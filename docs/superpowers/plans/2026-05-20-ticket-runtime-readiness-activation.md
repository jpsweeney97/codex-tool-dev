# Ticket Runtime Readiness Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add activation-capable Ticket runtime readiness for T-20260518-02, proving that the installed Codex runtime demonstrably routes canonical Ticket mutation commands through the installed Ticket hook before activation-gated `auto_audit` execute workflows rely on stronger readiness.

**Architecture:** Keep Ticket's existing guarded provenance/trust model, but redefine the hook's role before adding the activation layer. The hook is a runtime wiring witness and command/payload membrane, not a source of security-grade agent identity. The activation layer has three parts: a Ticket-owned app-server inventory collector, an activation-mode `ticket_doctor.py` command that runs live Codex-mediated hook membrane smokes, and an `engine_execute()` gate that reloads `.codex/ticket-runtime-proof.json` only as an index into recomputed local evidence. Source checkout diagnostics, fixture transcripts, direct hook-script runs, stale installed cache copies, and handwritten proof JSON alone can explain readiness failures but cannot activate runtime readiness; the gate must also re-parse semantically matching raw app-server JSON-RPC transcripts, recomputed normalized event rows, and current local hashes.

**Tech Stack:** Python >=3.11, pytest, Codex CLI `app-server` JSON-RPC, Codex CLI 0.132-compatible app-server turns, AgentControl child traversal smoke, project-local JSON proof files, bytecode-safe `uv run` verification.

---

## Decision Freeze

### Hook Role Reframing

Activation readiness proves installed hook-mediated mutation wiring, not caller
identity. Current Codex 0.132 does not expose spawned-agent identity in
`PreToolUse`; therefore `agent_id` must not be a readiness prerequisite unless
the Codex hook contract changes.

The readiness boundary is:

> Ticket mutations are activation-ready when the installed Codex runtime
> demonstrably routes canonical Ticket mutation commands through the installed
> Ticket hook, the hook validates the command/payload membrane, injects host
> session context, and `execute` refuses mutation without that hook-mediated
> provenance.

Consequences for this plan:

- `agent_id` is not required for activation readiness.
- `hook_request_origin` is observed provenance metadata, not a security-grade
  agent identity claim.
- Current Codex 0.132 hook stdin has no agent identity field, even for
  AgentControl-spawned child turns.
- The activation proof must accept `hook_request_origin == "user"` for current
  installed runtime.
- `ticket_engine_agent.py` remains the policy-selecting entrypoint for
  `request_origin == "agent"`, but the hook-observed origin is no longer
  required to match that entrypoint until Codex exposes a host-owned agent
  identity signal.
- AgentControl child smoke is required only to prove child Bash execution
  traverses the same installed hook membrane.
- Proof language should use `runtime_wiring_proof`, `hook_membrane_proof`,
  `installed_ticket_runtime_readiness`, and
  `agentcontrol_hook_traversal_smoke` instead of caller-identity proof.

Live evidence captured on 2026-05-20:

- Nested `codex exec` and real AgentControl-spawned child turns both fired the
  installed Ticket hook and injected `hook_request_origin="user"`.
- A trusted disposable raw hook logger captured the AgentControl child
  `PreToolUse` stdin. Its top-level keys were `cwd`, `hook_event_name`,
  `model`, `permission_mode`, `session_id`, `tool_input`, `tool_name`,
  `tool_use_id`, `transcript_path`, and `turn_id`; there was no `agent_id`,
  `agents_id`, `agentId`, or other agent-bearing field.
- Evidence artifacts:
  `/private/tmp/codex-appserver-raw-hook-agentcontrol-20260520T061501Z/summary.json`
  and
  `/private/tmp/codex-appserver-raw-hook-agentcontrol-20260520T061501Z/raw_hook_events.jsonl`.

Fresh 0.132.0 schema evidence captured on 2026-05-20:

- `codex --version` reported `codex-cli 0.132.0`.
- Schema was regenerated with `codex app-server generate-json-schema
  --experimental --out
  /private/tmp/ticket-runtime-readiness-schema-review-codex-0.132.0-20260520-fresh`.
- The regenerated schema shows `thread/start` and `turn/start` both accept
  `approvalPolicy`, `approvalsReviewer`, and `cwd`;
  `thread/start` accepts `sandbox` / `runtimeWorkspaceRoots`, and `turn/start`
  accepts `sandboxPolicy` / `runtimeWorkspaceRoots`.
- The regenerated schema shows the server can emit
  `item/commandExecution/requestApproval` during `turn/start` turns, with
  command, cwd, available decisions, and proposed policy amendments in
  `CommandExecutionRequestApprovalParams`.

| Area | Frozen decision |
| --- | --- |
| Activation owner | Ticket owns the activation producer inside `plugins/turbo-mode/ticket/scripts/`. Do not import the refresh-tool package at plugin runtime. Copy or extract only constants-free patterns as needed. |
| Proof class | `.codex/ticket-runtime-proof.json` is installed-runtime activation proof, not source proof, cache proof, or docs readiness. During activation closeout, `.codex/ticket-runtime-proof.candidate.json` may hold `status="activation_in_progress"` candidate evidence, but normal gated execute must reject that status/path. |
| Proof root vs smoke root | The proof field `project_root` is the proof target project root: the real repository being activated. The activation and post-proof smoke workspaces are disposable smoke project roots under `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/` and may contain their own `.codex/` marker for contained config. Gate code must never derive the proof target root from the smoke `tickets_dir`; post-proof smoke execute must receive an internal proof-root channel or derive it from the exact payload path before loading candidate/final proof. |
| App-server inventory | Activation inventory must be collected live by the activation command through `codex app-server --listen stdio://`. Operator-supplied inventory files are diagnostics only. |
| Inventory authority | Activation inventory requests must bind `marketplacePath`, `remoteMarketplaceName`, and `cwds=[PROJECT_ROOT]` explicitly. The default marketplace path for this repo is `<REPO_ROOT>/.agents/plugins/marketplace.json`; activation may read it but must not write it. |
| Inventory methods | Activation inventory must include `initialize`, the id-less `initialized` notification, `plugin/read`, `plugin/list`, `skills/list`, and `hooks/list`. `plugin/read` and `plugin/list` must use the same explicit marketplace binding, and `skills/list` / `hooks/list` must use the same explicit cwd binding. |
| Installed runtime identity | `plugin/read` is marketplace/source metadata, not installed-root proof. The installed runtime root is derived from `hooks/list.sourcePath` and the guard command, then corroborated by `skills/list` cache-backed Ticket skill paths. |
| Hook identity | The proof must bind `hook_manifest_path`, `hook_manifest_sha256`, `guard_command`, `guard_script_path`, `guard_script_sha256`, and `installed_cache_root` separately. `plugin/read` source must remain a separate source-authority field. |
| Hook count | Runtime inventory must prove exactly one Ticket Bash `preToolUse` guard for `ticket@turbo-mode`. Zero, duplicate, warning, error, or wrong-command hook entries fail activation. |
| Smoke path | Activation smoke must run through Codex app-server, not by invoking `ticket_engine_guard.py` directly. The activation-gate smoke is a normal app-server turn running one canonical Ticket mutation command with `cwd=<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/`, treating that run directory as a disposable project root. A second AgentControl-spawned child smoke corroborates that child Bash execution traverses the same installed hook membrane. |
| App-server turn policy | Every app-server smoke turn must pin `approvalPolicy="never"`, a contained `cwd`, explicit runtime workspace roots, and a workspace-write sandbox policy whose writable root is the contained smoke project root. Activation must fail closed if any `item/commandExecution/requestApproval`, file-change approval, permissions approval, or sandbox-escalation request appears; do not auto-approve or wait for an operator decision. This is based on the live 0.132.0 schema regenerated at `/private/tmp/ticket-runtime-readiness-schema-review-codex-0.132.0-20260520-fresh`. The 2026-05-20 narrow same-thread preflight found that this Mac's current `workspaceWrite` smoke can fail before the command with `sandbox-exec: sandbox_apply: Operation not permitted`; that is an environment/schema diagnostic, not permission to fall back to `dangerFullAccess` for activation. The same preflight's `dangerFullAccess` run against a disposable project root is diagnostic only and proved session stability, not activation readiness. |
| Activation bootstrap | First activation cannot depend on the proof it is creating. The smoke command must use a dedicated installed entrypoint, `ticket_engine_activation_smoke.py execute <payload>`, that still goes through Bash, the installed Ticket hook, the existing trust triple, `auto_audit`, dedup, and audit writes, but passes `runtime_readiness_required=False` only after it validates that `cwd`, payload path, and `tickets_dir` are contained under `.codex/ticket-runtime-smoke/<run_nonce>/`. This bootstrap path is not an external `execute_surface` value and cannot be selected by payload fields, wrapper scripts, normal `ticket_engine_agent.py`, `capture_execute`, or `update_execute`. |
| Smoke project setup | The smoke run directory must contain its own `.codex/ticket.local.md` with `autonomy_mode: auto_audit` before the turn starts. The execute payload must include an `autonomy_config` snapshot matching that file. Activation must not require the real target project to have `.codex/ticket.local.md`; the real project root remains the proof target, while the smoke project is only a contained execution fixture. |
| Smoke membrane | The activation smoke must prove hook membrane traversal: canonical `ticket_engine_activation_smoke.py execute`, exactly one matching `commandExecution` item, exactly one matching installed hook completion on the same turn, hook run `status=="completed"`, no unsupported hook-output warning, no `unsupported permissionDecision` run entry, `hook_injected is True`, `hook_request_origin == "user"` on current Codex, non-empty host `session_id`, command/payload/nonce binding, and `execute` success. AgentControl child smoke must prove a child turn fires the same installed hook for the canonical command, but it must not require `hook_request_origin == "agent"`. The observed installed-cache behavior on 2026-05-20 still emitted `PreToolUse hook returned unsupported permissionDecision: allow` with `hook/completed.status=="failed"` while injecting payloads; that remains a blocker until the hook output contract is fixed and tested. |
| Smoke result binding | `execute` success cannot be accepted from normalized proof JSON alone. The gate must hash and parse `raw/engine-stdout.json`, verify `state == "ok_create"`, `ticket_id`, nonce, payload path, and smoke tickets dir, then verify the created ticket file and the `.audit/YYYY-MM-DD/<session_id>.jsonl` entries exist under the disposable smoke tickets dir. |
| Smoke mutation | The smoke may write only inside `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/` before proof promotion. The disposable smoke project may create its own `.codex/ticket.local.md` and `docs/tickets/` under that run directory. It must not create or mutate the target project's normal `docs/tickets/` files or target project `.codex/ticket.local.md`. |
| Proof write | The final activation proof path is `<PROJECT_ROOT>/.codex/ticket-runtime-proof.json`. The temporary closeout candidate path is `<PROJECT_ROOT>/.codex/ticket-runtime-proof.candidate.json` and is non-authorizing for normal execute. Raw app-server JSON-RPC transcripts use `{"direction": "send"|"recv", "body": ...}` rows. Normalized hook membrane and AgentControl event artifacts are derived from those raw transcript rows and hashed separately; they are not independent evidence and must be recomputed by the verifier. Engine output and copied payloads stay under `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/raw/` with `0600` files where practical. The smoke ticket/audit artifacts stay under `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/docs/tickets/`. The proof JSON is only an index to this raw evidence; if the run directory or any required raw artifact is deleted, activation is invalid until rerun. |
| Local activation artifacts | Do not add `.gitignore` rules in this implementation slice. Treat `.codex/ticket-runtime-proof.json`, `.codex/ticket-runtime-proof.candidate.json`, and `.codex/ticket-runtime-smoke/` as local runtime artifacts: source-only work must not create them, optional live activation may create them, final closeout must report them explicitly with a scoped untracked status check plus a scoped ignored-artifact check, and none may be staged or committed. Cleanup, `git clean`, or deleting `.codex/ticket-runtime-smoke/<run_nonce>/raw/` invalidates the proof even before `expires_at`; rerun activation instead of treating the surviving proof JSON as authoritative. |
| Nonce binding | One fresh `run_nonce` must appear in inventory evidence, smoke payload data, smoke result, and final proof. Mismatched or missing nonce fails activation. |
| Source checkout | Running activation from the source checkout may report diagnostics, but it must not write `.codex/ticket-runtime-proof.json`. Activation derives the running plugin root from `Path(__file__).resolve().parents[1]`; no CLI argument may impersonate the running root. Activation succeeds only when the derived running plugin root equals the installed cache root proven by app-server `hooks/list` and corroborated by installed-cache `skills/list` paths. |
| Agent policy selectors | The hook-observed origin and payload fields are not policy selectors. `direct_execute` uses the hardcoded `ticket_engine_agent.py` entrypoint. Wrapper surfaces require hardcoded agent wrapper entrypoints that pass `request_origin="agent"` internally; the existing user wrappers remain `request_origin="user"`. |
| Wrapper hook membrane | New agent wrapper entrypoints must be explicitly allowlisted by `ticket_engine_guard.py` and covered by `tests/test_hook.py`. An unrecognized `ticket_*.py` script remains denied by the hook. |
| Wrapper prepare/execute fingerprint | Capture/update post-proof smokes must not prepare wrapper payloads through a different trust path than execute. `capture_execute` and `update_execute` must run both `prepare` and `execute` through app-server, the installed hook, and the same hardcoded agent wrapper entrypoint in the same app-server thread/session. Before relying on those post-smokes, run a narrow live preflight against the installed hook that executes two hook-mediated turns in one app-server thread and proves `session_id`, `hook_injected`, and `hook_request_origin` are stable from prepare to execute. The 2026-05-20 preflight proved same-thread `session_id` stability under diagnostic `dangerFullAccess` against a disposable project root, while `workspaceWrite` failed before command execution; implementation must still prove the pinned workspace-write policy or stop with a policy diagnostic. Activation must record and verify that the wrapper execute-fingerprint trust inputs are stable from the prepared payload to the execute payload: non-empty `session_id`, `hook_injected is True`, `hook_request_origin == "user"` on current Codex, contained `tickets_dir`, payload path, and saved `execute_fingerprint`. A `stale_plan` before the readiness gate is an activation failure unless the implementation intentionally changes the wrapper fingerprint contract and adds tests for the new behavior. |
| Gate scope | `engine_execute()` readiness gating applies only to `request_origin == "agent"` execute surfaces that can mutate tickets under `auto_audit`: `direct_execute`, `capture_execute`, and `update_execute`. `capture_execute` and `update_execute` are in scope only after the dedicated agent wrapper entrypoints select `request_origin="agent"` without trusting hook-origin metadata or caller payload. The gate does not apply to ingest because ingest is an internal dispatch path, not an external `execute_surface` value; it already requires the guarded engine entrypoints and remains governed by the existing trust triple plus ingest policy. The internal `activation_smoke` bootstrap path is excluded only for the dedicated activation-smoke entrypoint and only for the contained smoke tickets directory. |
| Gate order | The readiness gate runs after the existing hook trust triple and structural execute prerequisites, and before ticket mutation/audit writes. Existing lower-level policy failures should not be hidden by a readiness error when the request is already untrusted or malformed. |
| Gate verification | The gate must treat proof JSON as untrusted input and recompute bound identity at gate time: current plugin manifest SHA256, hook manifest SHA256, guard script SHA256, guard command/script SHA256, installed code identity for every installed Ticket `scripts/*.py` file plus separate hook/manifests, Codex executable identity, plugin/read source metadata, installed-root hook/skill evidence, inventory transcript hash, aggregate app-server transcript hash after all appends, raw JSON-RPC transcript semantics, normalized event rows recomputed from raw transcripts, raw evidence containment/existence, smoke command identity backed by `commandExecution`, hook completion backed by `hook/completed`, smoke payload hashes or wrapper payload snapshots/deletion status, wrapper trust-fingerprint stability for capture/update, engine stdout hash/result semantics, smoke ticket/audit artifacts, nonce, age, and closeout-level `post_activation_gated_smokes` for the current `execute_surface`. The exported proof verifier must fail closed on unknown surfaces; ingest and other non-gated internal paths must bypass the verifier before calling it, not by relying on a silent return. A well-shaped handwritten JSON file must fail without matching raw evidence, raw evidence semantics, current hashes, and the current surface's post-proof smoke. |
| Post-proof gated smokes | Activation is not complete when the bootstrap candidate verifies. After the candidate proof is written to `.codex/ticket-runtime-proof.candidate.json`, the installed activation command must run live app-server smokes through the actual gated surfaces with `runtime_readiness_required=True`: `ticket_engine_agent.py execute` for `direct_execute`, hook-mediated `ticket_capture_agent.py prepare` then `ticket_capture_agent.py execute` for `capture_execute`, and hook-mediated `ticket_update_agent.py prepare` then `ticket_update_agent.py execute` for `update_execute`. These smokes must use a candidate-only verifier mode that ignores any existing final proof and accepts only the fresh candidate nonce, expected surface, normalized current command identity (`python3` with optional single `-B`), exact payload path, contained post-smoke tickets dir, and proof target project root. A stale activated `.codex/ticket-runtime-proof.json` must not authorize activation closeout smokes for a new candidate. The candidate must never authorize normal target-project `docs/tickets` mutation. The final activated proof must not be written until every surface listed in `gated_execute_surfaces` has passing post-proof smoke evidence, and normal `engine_execute()` must reject an activated proof if the requested surface lacks that closeout evidence. Activation fails if any gated surface is missing, blocked, stale, not hook-mediated, or not mechanically executable from its wrapper contract. If implementation intentionally narrows activation to direct execute only, the proof and docs must narrow `gated_execute_surfaces` to `["direct_execute"]`; do not keep capture/update in scope without proving them. |
| Runtime freshness | The gate proof is valid only for the current project root, Ticket plugin id/version, installed cache root derived from hook identity, plugin/read source metadata, plugin manifest SHA256, installed code identity hashes, guard script SHA256, hook manifest SHA256, Codex executable identity, inventory transcript hash, aggregate app-server transcript hash, raw evidence hashes and semantics, exact smoke command/cwd backed by schema-shaped `commandExecution`, hook completion backed by schema-shaped `hook/completed`, payload hashes or wrapper payload snapshots/deletion status, capture/update trust-fingerprint stability, parsed engine result, smoke ticket/audit artifacts, nonce, current-surface post-proof smoke evidence, and a bounded age. Activation closeout additionally requires post-proof gated smoke evidence for every surface listed in `gated_execute_surfaces`. Use a default max age of 24 hours. |
| Cache mutation | This plan does not install, refresh, rewrite, or sync the installed plugin cache. Activation must fail when the executing plugin root is the source checkout, when installed-cache identity does not match the live `hooks/list` / `skills/list` evidence, or when installed code hashes differ from the proof. Do not claim broad source-vs-cache digest equality unless the implementation adds an explicit source manifest digest comparison; otherwise report source/cache drift as a diagnostic only. |
| Source closeout | Source implementation closeout can prove that source code and tests are ready. It cannot by itself produce installed activation. Installed activation is a separate explicit post-refresh operation against the installed cache copy. |
| Test seams | Source tests may inject an executing plugin root, verifier function, or activation collaborator through direct in-process helper calls only. Production code must default to `Path(__file__).resolve().parents[1]` and must not expose `--plugin-root`, `--cache-root`, payload fields, or environment variables that can impersonate installed-cache execution or supply non-live readiness evidence. The live hook and activation app-server child environment must not trust ambient `CODEX_PLUGIN_ROOT`; remove that override from production lookup or scope it behind an explicit pytest-only helper, unset it for activation child processes, and add regression tests proving a malicious inherited value cannot make source checkout execution look installed. |
| Parallel agents | This plan does not serialize parallel autonomous ticket creation. T-20260518-01 remains the separate multi-writer follow-up. |

## Non-Goals

- Do not mutate `/Users/jp/.codex/plugins/cache`.
- Do not run guarded refresh, personal-plugin sync, plugin install, or marketplace edits.
- Do not claim installed runtime readiness from source file presence, cache file presence, docs, or fixture output.
- Do not claim installed activation from a source-only implementation branch before an explicit refresh puts the new activation code in the installed cache.
- Do not accept a direct `ticket_engine_guard.py` subprocess run as activation smoke.
- Do not require `hook_request_origin == "agent"` for activation on current Codex. Treat `hook_request_origin` as hook-observed provenance metadata unless the Codex hook contract gains a host-owned agent identity signal.
- Do not use AgentControl child smoke as a caller-identity proof. It is only a traversal proof for the installed hook membrane.
- Do not let ordinary `ticket_engine_agent.py`, capture, update, or payload-controlled fields select the activation bootstrap bypass.
- Do not let `ticket_doctor.py diagnose --runtime-probe-output` write or promote the activation proof.
- Do not add a production `ticket_doctor.py` environment-variable fixture path for `activate-runtime`; non-live fixtures must stay in pytest-only helper code outside the installed command path.
- Do not rely on ambient `CODEX_PLUGIN_ROOT` for production hook, doctor, or activation root discovery.
- Do not use `dangerFullAccess` as an activation fallback when the pinned workspace-write app-server policy fails. It is allowed only as a diagnostic preflight result that must be labeled non-authorizing.
- Do not add locking or queueing for parallel autonomous ticket creation.
- Do not broaden `auto_silent`.
- Do not change the Ticket hook fail-open crash posture.
- Do not gate read-only Ticket operations.
- Do not let external `execute` payloads set `execute_surface="ingest"` or any internal bypass label.

## Source Files To Read First

Before implementation, re-read these live files. This plan and historical memory are not substitutes for current source truth.

- `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`
- `docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md`
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- `plugins/turbo-mode/ticket/hooks/hooks.json`
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_agent.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_paths.py`
- `plugins/turbo-mode/ticket/scripts/ticket_trust.py`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- `plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py`

## File Structure

- `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md` - this control document.
- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py` - new Ticket-owned runtime inventory, live smoke, activation-proof writer, and proof validator. This file must not import from `plugins/turbo-mode/tools/refresh`.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - add `activate-runtime` command and wire activation diagnostics.
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py` - keep `diagnose` read-only; optionally report activation-proof status without promoting proof.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py` - new dedicated activation bootstrap entrypoint. It is allowed to bypass the readiness proof only for the contained smoke tickets dir after hook mediation and smoke-root validation.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` - add `execute_surface` parameter and activation runtime-readiness gate for `request_origin == "agent"` / `auto_audit`.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - parse and pass `execute_surface`, defaulting direct engine execute to `direct_execute`; keep ingest excluded.
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py` - add `ExecuteInput.execute_surface` with strict accepted values.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - set `execute_surface="capture_execute"` before dispatching execute.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - set `execute_surface="update_execute"` before dispatching execute.
- `plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py` - new hardcoded agent wrapper entrypoint for capture prepare/execute policy selection.
- `plugins/turbo-mode/ticket/scripts/ticket_update_agent.py` - new hardcoded agent wrapper entrypoint for update prepare/execute policy selection.
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py` - align allow/deny output with the Codex app-server hook contract and allow the activation-smoke entrypoint plus canonical agent wrapper entrypoints through the same command/payload membrane as the user wrappers.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - document activation proof, proof classes, gate scope, and diagnostics-only evidence.
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py` - map runtime-readiness errors to explicit recovery guidance.
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` - add explicit activation workflow, including the fact that activation runs live Codex and writes `.codex/ticket-runtime-proof.json` only on success.
- `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py` - new focused unit tests for inventory parsing, smoke validation, proof writing, source-vs-installed rejection, freshness, and gate validation.
- `plugins/turbo-mode/ticket/tests/test_doctor.py` - activation command CLI tests and diagnostics-only guard tests.
- `plugins/turbo-mode/ticket/tests/test_engine_runner.py` - runner context payload-path, command-identity, proof-root, and execute-only channel coverage.
- `plugins/turbo-mode/ticket/tests/test_execute.py` - engine gate coverage for agent execute surfaces.
- `plugins/turbo-mode/ticket/tests/test_capture.py` - capture execute surface coverage.
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py` - update execute surface coverage.
- `plugins/turbo-mode/ticket/tests/test_ingest.py` - explicit regression that ingest is not gated by activation proof.
- `plugins/turbo-mode/ticket/tests/test_hook.py` - hook output contract and agent wrapper membrane coverage.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` - static docs/skill contract checks.
- `plugins/turbo-mode/ticket/tests/test_ux.py` - runtime-readiness error guidance coverage.

## Activation Proof Schema

The final proof file must be small and commit-safe enough to inspect, but it still lives under project-local `.codex/` rather than tracked docs. Raw transcripts stay in the run directory.

During activation, the command may write an intermediate candidate proof to
`.codex/ticket-runtime-proof.candidate.json` with
`status="activation_in_progress"`. That candidate is an index for the contained
post-proof smoke only. `verify_activation_closeout_proof_for_execute()` and
ordinary agent `auto_audit` execute must reject it. Only the candidate-only
`verify_activation_candidate_for_post_smoke()` mode may accept it, and only when
the current command matches the candidate `run_nonce`, expected surface, exact
payload path, contained post-smoke tickets dir, and proof target project root.
This mode must run before any final-proof lookup and must not fall back to an
older activated proof. The smoke project root is not the proof target root even
when it has its own `.codex/` marker.

The base verifier that proves installed roots, inventory, bootstrap smoke, and
raw evidence is a private helper named
`_verify_activation_bootstrap_base_proof_for_execute()`. Normal execute and
closeout code must call `verify_activation_closeout_proof_for_execute()`, which
also verifies `post_activation_gated_smokes` for the current surface. Do not
export or route normal gates through the private bootstrap helper.

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
  "installed_code_identity": {
    "hash_algorithm": "sha256",
    "paths": {
      "scripts/__init__.py": "<sha256>",
      "scripts/ticket_audit.py": "<sha256>",
      "scripts/ticket_capture.py": "<sha256>",
      "scripts/ticket_capture_agent.py": "<sha256>",
      "scripts/ticket_dedup.py": "<sha256>",
      "scripts/ticket_doctor.py": "<sha256>",
      "scripts/ticket_engine_activation_smoke.py": "<sha256>",
      "scripts/ticket_engine_agent.py": "<sha256>",
      "scripts/ticket_engine_core.py": "<sha256>",
      "scripts/ticket_engine_runner.py": "<sha256>",
      "scripts/ticket_engine_user.py": "<sha256>",
      "scripts/ticket_envelope.py": "<sha256>",
      "scripts/ticket_id.py": "<sha256>",
      "scripts/ticket_parse.py": "<sha256>",
      "scripts/ticket_paths.py": "<sha256>",
      "scripts/ticket_payloads.py": "<sha256>",
      "scripts/ticket_read.py": "<sha256>",
      "scripts/ticket_render.py": "<sha256>",
      "scripts/ticket_review.py": "<sha256>",
      "scripts/ticket_runtime_readiness.py": "<sha256>",
      "scripts/ticket_stage_models.py": "<sha256>",
      "scripts/ticket_triage.py": "<sha256>",
      "scripts/ticket_trust.py": "<sha256>",
      "scripts/ticket_update.py": "<sha256>",
      "scripts/ticket_update_agent.py": "<sha256>",
      "scripts/ticket_ux.py": "<sha256>",
      "scripts/ticket_validate.py": "<sha256>",
      "scripts/ticket_workflow.py": "<sha256>"
    }
  },
  "runtime_identity": {
    "codex_version": "codex-cli 0.x.y",
    "executable_path": "/absolute/path/to/codex",
    "executable_sha256": "<sha256-or-null>",
    "executable_hash_unavailable_reason": null,
    "server_info": {},
    "initialize_capabilities": {},
    "accepted_response_schema_version": "ticket-app-server-readonly-inventory-v1",
    "parser_version": "installed-ticket-runtime-readiness-1"
  },
  "app_server_transcript_sha256": "<sha256-of-complete-transcript-after-inventory-and-smokes>",
  "inventory": {
    "request_methods": ["initialize", "initialized", "plugin/read", "plugin/list", "skills/list", "hooks/list"],
    "marketplace_path": "/Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json",
    "remote_marketplace_name": null,
    "cwd": "/absolute/project/root",
    "transcript_sha256": "<sha256-of-raw/app-server-inventory-transcript.jsonl>",
    "plugin_read_source_path": "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket",
    "plugin_read_source_sha256": "<sha256-of-normalized-plugin-read-summary>",
    "installed_runtime_root": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0",
    "installed_runtime_root_evidence": "hooks/list.sourcePath",
    "ticket_skill_names": ["ticket:ticket-capture", "ticket:ticket-update", "ticket:ticket-find", "ticket:ticket-review", "ticket:ticket-doctor"],
    "ticket_skill_paths": [
      "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/skills/ticket-capture/SKILL.md",
      "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/skills/ticket-update/SKILL.md",
      "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/skills/ticket-find/SKILL.md",
      "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/skills/ticket-review/SKILL.md",
      "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/skills/ticket-doctor/SKILL.md"
    ],
    "hook": {
      "plugin_id": "ticket@turbo-mode",
      "event_name": "preToolUse",
      "matcher": "Bash",
      "source_path": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json",
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
    "turn_status": "completed",
    "raw_hook_events_sha256": "<sha256>",
    "payload_sha256_before": "<sha256>",
    "payload_sha256_after": "<sha256>",
    "smoke_project_root": ".codex/ticket-runtime-smoke/<run_nonce>",
    "cwd": ".codex/ticket-runtime-smoke/<run_nonce>",
    "autonomy_config_path": ".codex/ticket-runtime-smoke/<run_nonce>/.codex/ticket.local.md",
    "autonomy_config": {"mode": "auto_audit", "max_creates": 3, "warnings": []},
    "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_engine_activation_smoke.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/payload.json",
    "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/payload.json",
    "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets",
    "payload_tickets_dir": "docs/tickets",
    "hook_request_origin": "user",
    "hook_injected": true,
    "session_id": "<non-empty-codex-session-id>",
    "nonce": "ticket-runtime-20260520T000000Z-0123456789abcdef",
    "engine_stdout_sha256": "<sha256>",
    "engine_state": "ok_create",
    "ticket_id": "T-20260520-01",
    "ticket_path": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets/2026-05-20-example.md",
    "ticket_sha256": "<sha256>",
    "audit_file_path": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets/.audit/2026-05-20/<safe-session-id>.jsonl",
    "audit_file_sha256": "<sha256>"
  },
  "agentcontrol_hook_traversal_smoke": {
    "runner": "app_server_agentcontrol",
    "status": "passed",
    "parent_thread_id": "<parent-thread-id>",
    "child_thread_id": "<child-thread-id>",
    "child_turn_id": "<child-turn-id>",
    "raw_hook_events_sha256": "<sha256>",
    "payload_sha256_after": "<sha256>",
    "installed_hook_source_path": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json",
    "smoke_project_root": ".codex/ticket-runtime-smoke/<run_nonce>",
    "cwd": ".codex/ticket-runtime-smoke/<run_nonce>",
    "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_engine_activation_smoke.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/agentcontrol-payload.json",
    "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/agentcontrol-payload.json",
    "payload_tickets_dir": "docs/tickets",
    "hook_request_origin": "user",
    "hook_injected": true,
    "nonce": "ticket-runtime-20260520T000000Z-0123456789abcdef"
  },
  "post_activation_gated_smokes": {
    "status": "passed",
    "required_surfaces": ["direct_execute", "capture_execute", "update_execute"],
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
      },
      "capture_execute": {
        "runner": "app_server_turn",
        "prepare_command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_capture_agent.py prepare /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/post-capture/post-capture-payload.json",
        "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_capture_agent.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/post-capture/post-capture-payload.json",
        "execute_surface": "capture_execute",
        "runtime_readiness_required": true,
        "engine_state": "ok_create",
        "raw_events_sha256": "<sha256>",
        "engine_stdout_sha256": "<sha256>",
        "wrapper_trust_fingerprint_inputs": {
          "prepared": {
            "session_id": "<non-empty-codex-session-id>",
            "hook_injected": true,
            "hook_request_origin": "user",
            "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/post-capture/docs/tickets",
            "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-capture/post-capture-payload.json",
            "saved_execute_fingerprint": "<sha256>"
          },
          "execute_time": {
            "session_id": "<same-non-empty-codex-session-id>",
            "hook_injected": true,
            "hook_request_origin": "user",
            "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/post-capture/docs/tickets",
            "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-capture/post-capture-payload.json",
            "recomputed_execute_fingerprint": "<same-sha256>"
          },
          "stable_between_prepare_and_execute": true
        },
        "ticket_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-capture/docs/tickets/2026-05-20-example.md",
        "ticket_sha256": "<sha256>"
      },
      "update_execute": {
        "runner": "app_server_turn",
        "prepare_command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_update_agent.py prepare /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/post-update/post-update-payload.json",
        "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_update_agent.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/post-update/post-update-payload.json",
        "execute_surface": "update_execute",
        "runtime_readiness_required": true,
        "engine_state": "ok_update",
        "raw_events_sha256": "<sha256>",
        "engine_stdout_sha256": "<sha256>",
        "wrapper_trust_fingerprint_inputs": {
          "prepared": {
            "session_id": "<non-empty-codex-session-id>",
            "hook_injected": true,
            "hook_request_origin": "user",
            "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/post-update/docs/tickets",
            "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-update/post-update-payload.json",
            "saved_execute_fingerprint": "<sha256>"
          },
          "execute_time": {
            "session_id": "<same-non-empty-codex-session-id>",
            "hook_injected": true,
            "hook_request_origin": "user",
            "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/post-update/docs/tickets",
            "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-update/post-update-payload.json",
            "recomputed_execute_fingerprint": "<same-sha256>"
          },
          "stable_between_prepare_and_execute": true
        },
        "ticket_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-update/docs/tickets/2026-05-20-example.md",
        "ticket_sha256": "<sha256>"
      }
    }
  },
  "activation_scope": {
    "gated_execute_surfaces": ["direct_execute", "capture_execute", "update_execute"],
    "excluded_mutation_paths": ["ingest_dispatch", "activation_smoke_bootstrap"],
    "request_origin": "agent",
    "hook_request_origin_contract": "metadata_only_currently_user",
    "autonomy_mode": "auto_audit"
  },
  "raw_evidence": {
    "run_dir": ".codex/ticket-runtime-smoke/<run_nonce>",
    "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
    "app_server_transcript": "raw/app-server-transcript.jsonl",
    "hook_membrane_events": "raw/hook-membrane-events.jsonl",
    "agentcontrol_events": "raw/agentcontrol-events.jsonl",
    "post_activation_events": "raw/post-activation-gated-events.jsonl",
    "smoke_autonomy_config": ".codex/ticket.local.md",
    "payload_before": "raw/payload-before.json",
    "payload_after": "raw/payload-after.json",
    "wrapper_payload_before_prepare": "raw/<surface>-payload-before-prepare.json",
    "wrapper_payload_after_prepare": "raw/<surface>-payload-after-prepare.json",
    "wrapper_payload_before_execute": "raw/<surface>-payload-before-execute.json",
    "wrapper_payload_after_execute": "raw/<surface>-payload-after-execute.json",
    "wrapper_payload_deleted_after_execute": true,
    "agentcontrol_payload_after": "raw/agentcontrol-payload-after.json",
    "engine_stdout": "raw/engine-stdout.json",
    "engine_stderr": "raw/engine-stderr.txt"
  }
}
```

## Verification Harness

Focused tests while implementing:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_doctor.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_hook.py \
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
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_stage_models.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_update_agent.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
```

Whitespace gate:

```bash
git diff --check
```

CLI contract preflight for the live smoke command:

```bash
codex --version
codex app-server --help
```

Expected: `codex --version` reports `codex-cli 0.132.0` or a newer CLI whose app-server schema still exposes `thread/start`, `turn/start`, `hooks/list`, `plugin/read`, `plugin/list`, `skills/list`, `commandExecution` thread items, `hook/completed` notifications, and `collabAgentToolCall` thread items whose `tool` enum includes `spawnAgent`, `wait`, and `closeAgent`. Do not use `codex exec -a never` as the activation contract; the current proof boundary is app-server-mediated hook membrane traversal.

Live installed activation is explicit and not part of ordinary source verification. Run it only after the source implementation has been refreshed into the installed Ticket cache:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_doctor.py \
  activate-runtime /Users/jp/Projects/active/codex-tool-dev/docs/tickets \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

The absolute `docs/tickets` argument must be sufficient to bind
`PROJECT_ROOT=/Users/jp/Projects/active/codex-tool-dev`; activation must not
silently bind project root from the caller's cwd when an absolute tickets dir is
provided.

Expected live success shape after installed refresh: JSON response with `state: "ok"`, `data.mode: "activate-runtime"`, `data.proof_path: "<PROJECT_ROOT>/.codex/ticket-runtime-proof.json"`, and `data.proof.status: "activated"`. In the source-only implementation slice, stale installed cache may fail with an unknown subcommand or missing activation behavior; report that as `source repaired, installed runtime not activated`.

## Stop Conditions

- If implementation cannot run a live hook-mediated smoke through Codex app-server without invoking `ticket_engine_guard.py` directly, stop and report the blocker. Do not weaken activation to direct hook subprocess proof.
- If app-server reports the installed Ticket hook output as unsupported, including the observed `permissionDecision: allow` warning shape, stop before the smoke harness and complete the hook-output contract preflight task. Do not defer this to installed activation closeout.
- If app-server turns cannot deterministically prove one canonical command, one installed hook invocation, one hook-injected payload, and nonce/payload binding, stop before writing proof.
- If the smoke run cannot create a contained disposable project root with `.codex/ticket.local.md` set to `auto_audit`, or if the execute payload cannot carry a matching `autonomy_config` snapshot, stop before writing proof.
- If the first live activation smoke hits `runtime_readiness_required` because it used a normal gated execute path instead of the dedicated activation-smoke bootstrap entrypoint, stop before writing proof.
- If the activation-smoke bootstrap can mutate outside the contained smoke tickets dir or can be selected by ordinary payload fields, stop before writing proof.
- If the proof does not bind installed code hashes for the activation entrypoint and gated execute path modules, stop before treating it as fresh.
- If AgentControl child smoke does not traverse the installed hook membrane, stop before claiming agent-workflow readiness. Do not reinterpret that as a caller-identity failure.
- If a future Codex release starts emitting a documented host-owned agent identity in `PreToolUse`, stop and update this plan's hook-origin semantics before using that field.
- If the current CLI app-server schema lacks the required thread/turn/hook/plugin/skill or AgentControl notification surfaces, stop and update the command contract before implementation.
- If app-server response schema drift changes `plugin/read`, `plugin/list`, `skills/list`, or `hooks/list`, stop and update the parser contract before continuing.
- If source execution tries to write `.codex/ticket-runtime-proof.json` or
  `.codex/ticket-runtime-proof.candidate.json`, stop. Source can diagnose but
  cannot activate.
- If activation would need to mutate `/Users/jp/.codex/plugins/cache`, stop and route that work through an explicit installed-refresh request.
- If source implementation has not been refreshed into `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0`, do not run the optional installed activation as an expected-success check.
- If a generated proof lacks nonce correlation between inventory, smoke, and proof, stop.
- If the smoke payload path, smoke tickets directory, or raw transcript path escapes `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/`, stop.
- If the runtime inventory has zero Ticket hooks, more than one Ticket hook, a non-Bash matcher, a non-`preToolUse` event, warnings/errors on the matching entry, or a guard command not under the installed Ticket cache root, stop.
- If `engine_execute()` starts gating `ingest`, read-only commands, or user-origin mutations, stop.
- If a test fixture or handwritten proof can make `engine_execute()` accept `request_origin=agent` `auto_audit` readiness, stop.
- If generated residue appears in plugin source paths (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, `.DS_Store`), clean it with `trash` only if cleanup is in scope, or report it before closeout.

## Commit Boundaries

- Commit 1: this plan only.
- Commit 2: runtime readiness schema, parser, and proof validator tests.
- Commit 3: Ticket-owned app-server inventory collector and parser.
- Commit 4: Ticket hook-output contract preflight and source tests.
- Commit 5: Codex-mediated live smoke harness and activation proof writer.
- Commit 6: `ticket_doctor.py activate-runtime` command and diagnostics wiring.
- Commit 7: `engine_execute()` gate plus execute-surface propagation.
- Commit 8: docs, skill wording, final focused/full verification.

---

### Task 0: Baseline And Branch Gate

**Files:**
- Read: `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md`
- Read: `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch and dirty state recorded. Preserve unrelated dirty work.

- [ ] **Step 2: Hard-stop on an unpublished or stale base**

```bash
git rev-list --left-right --count origin/main...HEAD
```

Expected: `0 0`. If the output is anything else, stop before creating the
implementation branch. Do not stack activation work on a locally ahead, behind,
or diverged `main` until the operator decides whether those commits are the
intended base, should be published first, or should be separated into a new
branch.

Current-checkout resolution path:

- If `main` is ahead only and those commits are the intended base, either
  publish them first and restart this task from updated `origin/main`, or create
  the implementation branch from the current `HEAD` only after recording that
  explicit base decision.
- If any ahead commit is unrelated to runtime readiness activation, split or
  rebase it away before continuing.
- If the plan file or other workspace files are dirty, commit, stash, or
  explicitly carry those edits before implementation starts. Do not mix
  pre-plan review edits with runtime implementation commits.

- [ ] **Step 3: Create the implementation branch if on `main`**

```bash
git branch --show-current
```

Expected: branch name recorded. If the output is `main`, run:

```bash
git switch -c feature/ticket-runtime-readiness-activation
```

Expected: current branch is `feature/ticket-runtime-readiness-activation`.

- [ ] **Step 4: Run the focused baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_doctor.py \
  tests/test_execute.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_docs_contract.py \
  -q
```

Expected: current focused status captured before source edits. If this fails, classify baseline failures before changing source.

- [ ] **Step 5: Record the Codex CLI activation-smoke contract**

```bash
codex --version
codex app-server --help
codex app-server generate-json-schema --experimental --out /private/tmp/ticket-runtime-readiness-schema
```

Expected: `codex --version` reports `codex-cli 0.132.0` or newer, `codex app-server --help` exits 0, and the `--experimental` schema contains `thread/start`, `turn/start`, `hooks/list`, `plugin/read`, `plugin/list`, `skills/list`, and AgentControl collaboration item fields. If these are absent or renamed, stop and update the smoke command contract before implementation.

- [ ] **Step 6: Commit the plan if requested**

```bash
git add docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md
git commit -m "docs: plan ticket runtime readiness activation"
```

Expected: only this plan is committed.

---

### Task 1: Runtime Readiness Schema And Proof Validator

**Files:**
- Create: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Create: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing schema tests**

Create `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py` with these initial tests:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.ticket_runtime_readiness import (
    ACTIVATING_EXECUTE_SURFACES,
    PROOF_SCHEMA_VERSION,
    REQUIRED_INSTALLED_CODE_PATHS,
    RuntimeReadinessError,
    build_activation_proof,
    candidate_proof_path_for_project,
    expected_installed_code_paths,
    normalize_app_server_jsonrpc_transcript,
    proof_path_for_project,
    sha256_regular_file,
    _verify_activation_bootstrap_base_proof_for_execute,
    verify_activation_closeout_proof_for_execute,
)


def _base_components(tmp_path: Path) -> dict[str, object]:
    project_root = tmp_path / "repo"
    source_root = project_root / "plugins/turbo-mode/ticket"
    installed_root = tmp_path / ".codex/plugins/cache/turbo-mode/ticket/1.4.0"
    run_nonce = "ticket-runtime-20260520T000000Z-abc123"
    run_dir = project_root / ".codex/ticket-runtime-smoke" / run_nonce
    raw_dir = run_dir / "raw"
    tickets_dir = run_dir / "docs/tickets"
    ticket_file = tickets_dir / "2026-05-20-example.md"
    audit_file = tickets_dir / ".audit/2026-05-20/host-session.jsonl"
    hook_manifest = installed_root / "hooks/hooks.json"
    guard_script = installed_root / "hooks/ticket_engine_guard.py"
    plugin_manifest = installed_root / ".codex-plugin/plugin.json"
    code_paths = [installed_root / rel_path for rel_path in sorted(REQUIRED_INSTALLED_CODE_PATHS)]
    for path in (hook_manifest, guard_script, plugin_manifest, *code_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")
    raw_dir.mkdir(parents=True, exist_ok=True)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    command = f"python3 -B {installed_root}/scripts/ticket_engine_activation_smoke.py execute {run_dir / 'payload.json'}"
    agent_command = f"python3 -B {installed_root}/scripts/ticket_engine_activation_smoke.py execute {run_dir / 'agentcontrol-payload.json'}"
    completed_at = 1_779_232_800_000

    def command_completed(*, thread_id: str, turn_id: str, item_id: str, command_text: str) -> dict[str, object]:
        return {
            "direction": "recv",
            "body": {
                "method": "item/completed",
                "params": {
                    "completedAtMs": completed_at,
                    "threadId": thread_id,
                    "turnId": turn_id,
                    "item": {
                        "type": "commandExecution",
                        "id": item_id,
                        "command": command_text,
                        "cwd": str(run_dir),
                        "status": "completed",
                        "commandActions": [],
                    },
                },
            },
        }

    def hook_completed(*, thread_id: str, turn_id: str, hook_id: str) -> dict[str, object]:
        return {
            "direction": "recv",
            "body": {
                "method": "hook/completed",
                "params": {
                    "threadId": thread_id,
                    "turnId": turn_id,
                    "run": {
                        "id": hook_id,
                        "displayOrder": 0,
                        "sourcePath": str(hook_manifest),
                        "eventName": "preToolUse",
                        "executionMode": "sync",
                        "handlerType": "command",
                        "scope": "turn",
                        "startedAt": completed_at - 10,
                        "completedAt": completed_at,
                        "status": "completed",
                        "entries": [],
                    },
                },
            },
        }

    app_rows = [
        {"direction": "send", "body": {"id": 0, "method": "initialize", "params": {}}},
        {"direction": "send", "body": {"method": "initialized"}},
        {"direction": "send", "body": {"id": 1, "method": "plugin/read", "params": {}}},
        {"direction": "send", "body": {"id": 2, "method": "plugin/list", "params": {}}},
        {"direction": "send", "body": {"id": 3, "method": "skills/list", "params": {}}},
        {"direction": "send", "body": {"id": 4, "method": "hooks/list", "params": {}}},
        {"direction": "send", "body": {"id": 5, "method": "thread/start", "params": {}}},
        {"direction": "send", "body": {"id": 6, "method": "turn/start", "params": {}}},
        command_completed(thread_id="parent-thread", turn_id="turn-1", item_id="cmd-1", command_text=command),
        hook_completed(thread_id="parent-thread", turn_id="turn-1", hook_id="hook-1"),
        {"direction": "recv", "body": {"method": "turn/completed", "params": {"threadId": "parent-thread", "turn": {"status": "completed"}}}},
        {"direction": "recv", "body": {"method": "item/completed", "params": {"completedAtMs": completed_at, "threadId": "parent-thread", "turnId": "turn-2", "item": {"type": "collabAgentToolCall", "id": "collab-1", "tool": "spawnAgent", "senderThreadId": "parent-thread", "receiverThreadIds": ["child-thread"], "status": "completed", "agentsStates": {"child-thread": {"status": "completed"}}}}}},
        command_completed(thread_id="child-thread", turn_id="child-turn-1", item_id="child-cmd-1", command_text=agent_command),
        hook_completed(thread_id="child-thread", turn_id="child-turn-1", hook_id="hook-2"),
        {"direction": "recv", "body": {"method": "turn/completed", "params": {"threadId": "child-thread", "turn": {"status": "completed"}}}},
    ]
    event_rows = normalize_app_server_jsonrpc_transcript(app_rows)
    (raw_dir / "app-server-inventory-transcript.jsonl").write_text(
        "\n".join(json.dumps(row) for row in app_rows[:6]) + "\n",
        encoding="utf-8",
    )
    (raw_dir / "app-server-transcript.jsonl").write_text(
        "\n".join(json.dumps(row) for row in app_rows) + "\n",
        encoding="utf-8",
    )
    (raw_dir / "hook-membrane-events.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in event_rows
            if row.get("threadId") == "parent-thread"
            and (row.get("turnId") == "turn-1" or row["method"] == "turn/completed")
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "agentcontrol-events.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in event_rows
            if row.get("threadId") == "child-thread"
            or row.get("item", {}).get("type") == "collabAgentToolCall"
        )
        + "\n",
        encoding="utf-8",
    )
    (raw_dir / "payload-before.json").write_text("{}", encoding="utf-8")
    (raw_dir / "payload-after.json").write_text("{}", encoding="utf-8")
    (raw_dir / "agentcontrol-payload-after.json").write_text("{}", encoding="utf-8")
    (raw_dir / "engine-stdout.json").write_text(
        json.dumps(
            {
        "state": "ok_create",
        "ticket_id": "T-20260520-01",
        "nonce": run_nonce,
        "payload_path": str(run_dir / "payload.json"),
        "tickets_dir": str(tickets_dir),
        "ticket_path": f".codex/ticket-runtime-smoke/{run_nonce}/docs/tickets/2026-05-20-example.md",
        "engine_response": {
            "state": "ok_create",
            "ticket_id": "T-20260520-01",
            "data": {"ticket_path": str(ticket_file)},
        },
    }
),
        encoding="utf-8",
    )
    ticket_file.write_text("id: T-20260520-01\n", encoding="utf-8")
    audit_file.write_text(
        '{"action":"attempt_started","session_id":"host-session","request_origin":"agent","autonomy_mode":"auto_audit","ticket_id":null}\n'
        '{"action":"create","result":"ok_create","session_id":"host-session","request_origin":"agent","autonomy_mode":"auto_audit","ticket_id":"T-20260520-01"}\n',
        encoding="utf-8",
    )
    return {
        "project_root": project_root,
        "source_root": source_root,
        "run_nonce": run_nonce,
        "run_dir": run_dir,
        "raw_dir": raw_dir,
        "ticket_file": ticket_file,
        "audit_file": audit_file,
        "created_at": datetime(2026, 5, 20, tzinfo=UTC),
        "installed_root": installed_root,
        "hook_manifest": hook_manifest,
        "guard_script": guard_script,
        "plugin_manifest": plugin_manifest,
    }


def test_proof_path_is_project_local_codex_file(tmp_path: Path) -> None:
    project_root = tmp_path / "repo"

    assert proof_path_for_project(project_root) == project_root / ".codex/ticket-runtime-proof.json"
    assert candidate_proof_path_for_project(project_root) == project_root / ".codex/ticket-runtime-proof.candidate.json"


def test_activation_proof_contains_required_identity_fields(tmp_path: Path) -> None:
    parts = _base_components(tmp_path)

    proof = build_activation_proof(
        project_root=parts["project_root"],
        run_nonce=parts["run_nonce"],
        created_at=parts["created_at"],
        status="activated",
        installed_cache_root=parts["installed_root"],
        plugin_manifest_path=parts["plugin_manifest"],
        runtime_identity={
            "codex_version": "codex-cli 0.test",
            "executable_path": "/usr/local/bin/codex",
            "executable_sha256": "abc",
            "executable_hash_unavailable_reason": None,
            "server_info": {"name": "codex-app-server"},
            "initialize_capabilities": {"experimentalApi": True},
        },
        inventory={
            "request_methods": ["initialize", "initialized", "plugin/read", "plugin/list", "skills/list", "hooks/list"],
            "marketplace_path": str(parts["project_root"] / ".agents/plugins/marketplace.json"),
            "remote_marketplace_name": None,
            "cwd": str(parts["project_root"]),
            "transcript_sha256": "inventory-sha",
            "plugin_read_source_path": str(parts["source_root"]),
            "plugin_read_source_sha256": "plugin-read-sha",
            "installed_runtime_root": str(parts["installed_root"]),
            "installed_runtime_root_evidence": "hooks/list.sourcePath",
            "ticket_skill_names": ["ticket:ticket-capture", "ticket:ticket-update", "ticket:ticket-find", "ticket:ticket-review", "ticket:ticket-doctor"],
            "ticket_skill_paths": [
                str(parts["installed_root"] / "skills/ticket-capture/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-update/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-find/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-review/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-doctor/SKILL.md"),
            ],
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "source_path": str(parts["hook_manifest"]),
                "hook_manifest_path": str(parts["hook_manifest"]),
                "hook_manifest_sha256": sha256_regular_file(parts["hook_manifest"]),
                "guard_command": f"python3 {parts['guard_script']}",
                "guard_script_path": str(parts["guard_script"]),
                "guard_script_sha256": sha256_regular_file(parts["guard_script"]),
            },
        },
        smoke={
            "runner": "app_server_turn",
            "status": "passed",
            "turn_status": "completed",
            "raw_hook_events_sha256": "events-sha",
            "payload_sha256_before": "payload-before-sha",
            "payload_sha256_after": "payload-after-sha",
            "smoke_project_root": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "cwd": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "autonomy_config_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/.codex/ticket.local.md",
            "autonomy_config": {"mode": "auto_audit", "max_creates": 3, "warnings": []},
            "command": f"python3 -B {parts['installed_root']}/scripts/ticket_engine_activation_smoke.py execute {parts['project_root']}/.codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "payload_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "tickets_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets",
            "payload_tickets_dir": "docs/tickets",
            "hook_request_origin": "user",
            "hook_injected": True,
            "session_id": "host-session",
            "nonce": parts["run_nonce"],
            "engine_stdout_sha256": sha256_regular_file(parts["raw_dir"] / "engine-stdout.json"),
            "engine_state": "ok_create",
            "ticket_id": "T-20260520-01",
            "ticket_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets/2026-05-20-example.md",
            "ticket_sha256": sha256_regular_file(parts["ticket_file"]),
            "audit_file_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets/.audit/2026-05-20/host-session.jsonl",
            "audit_file_sha256": sha256_regular_file(parts["audit_file"]),
        },
        raw_evidence={
            "run_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
            "app_server_transcript": "raw/app-server-transcript.jsonl",
            "hook_membrane_events": "raw/hook-membrane-events.jsonl",
            "agentcontrol_events": "raw/agentcontrol-events.jsonl",
            "post_activation_events": "raw/post-activation-gated-events.jsonl",
            "smoke_autonomy_config": ".codex/ticket.local.md",
            "payload_before": "raw/payload-before.json",
            "payload_after": "raw/payload-after.json",
            "agentcontrol_payload_after": "raw/agentcontrol-payload-after.json",
            "engine_stdout": "raw/engine-stdout.json",
            "engine_stderr": "raw/engine-stderr.txt",
        },
    )

    assert proof["schema_version"] == PROOF_SCHEMA_VERSION
    assert proof["status"] == "activated"
    assert proof["ticket_plugin"]["plugin_id"] == "ticket@turbo-mode"
    assert proof["ticket_plugin"]["version"] == "1.4.0"
    assert set(proof["installed_code_identity"]["paths"]) == set(expected_installed_code_paths(parts["installed_root"]))
    assert proof["installed_code_identity"]["paths"]["scripts/ticket_engine_core.py"] == sha256_regular_file(parts["installed_root"] / "scripts/ticket_engine_core.py")
    assert proof["installed_code_identity"]["paths"]["scripts/ticket_engine_activation_smoke.py"] == sha256_regular_file(parts["installed_root"] / "scripts/ticket_engine_activation_smoke.py")
    assert proof["inventory"]["hook"]["guard_script_sha256"] == sha256_regular_file(parts["guard_script"])
    assert proof["hook_membrane_smoke"]["nonce"] == proof["run_nonce"]
    assert proof["activation_scope"]["gated_execute_surfaces"] == list(ACTIVATING_EXECUTE_SURFACES)


def test_verify_activation_proof_rejects_source_root(tmp_path: Path) -> None:
    parts = _base_components(tmp_path)
    proof = build_activation_proof(
        project_root=parts["project_root"],
        run_nonce=parts["run_nonce"],
        created_at=parts["created_at"],
        status="activated",
        installed_cache_root=parts["installed_root"],
        plugin_manifest_path=parts["plugin_manifest"],
        runtime_identity={"codex_version": "codex-cli 0.test"},
        inventory={
            "request_methods": ["initialize", "initialized", "plugin/read", "plugin/list", "skills/list", "hooks/list"],
            "marketplace_path": str(parts["project_root"] / ".agents/plugins/marketplace.json"),
            "remote_marketplace_name": None,
            "cwd": str(parts["project_root"]),
            "transcript_sha256": "inventory-sha",
            "plugin_read_source_path": str(parts["source_root"]),
            "plugin_read_source_sha256": "plugin-read-sha",
            "installed_runtime_root": str(parts["installed_root"]),
            "installed_runtime_root_evidence": "hooks/list.sourcePath",
            "ticket_skill_names": ["ticket:ticket-capture", "ticket:ticket-update", "ticket:ticket-find", "ticket:ticket-review", "ticket:ticket-doctor"],
            "ticket_skill_paths": [
                str(parts["installed_root"] / "skills/ticket-capture/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-update/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-find/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-review/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-doctor/SKILL.md"),
            ],
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "source_path": str(parts["hook_manifest"]),
                "hook_manifest_path": str(parts["hook_manifest"]),
                "hook_manifest_sha256": sha256_regular_file(parts["hook_manifest"]),
                "guard_command": f"python3 {parts['guard_script']}",
                "guard_script_path": str(parts["guard_script"]),
                "guard_script_sha256": sha256_regular_file(parts["guard_script"]),
            },
        },
        smoke={
            "runner": "app_server_turn",
            "status": "passed",
            "turn_status": "completed",
            "raw_hook_events_sha256": "events-sha",
            "payload_sha256_before": "payload-before-sha",
            "payload_sha256_after": "payload-after-sha",
            "smoke_project_root": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "cwd": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "autonomy_config_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/.codex/ticket.local.md",
            "autonomy_config": {"mode": "auto_audit", "max_creates": 3, "warnings": []},
            "command": "python3 installed execute payload",
            "payload_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "tickets_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets",
            "payload_tickets_dir": "docs/tickets",
            "hook_request_origin": "user",
            "hook_injected": True,
            "session_id": "host-session",
            "nonce": parts["run_nonce"],
            "engine_state": "ok_create",
            "ticket_id": "T-20260520-01",
        },
        raw_evidence={
            "run_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
            "app_server_transcript": "raw/app-server-transcript.jsonl",
        },
    )

    with pytest.raises(RuntimeReadinessError, match="executing plugin root"):
        _verify_activation_bootstrap_base_proof_for_execute(
            proof,
            project_root=parts["project_root"],
            executing_plugin_root=tmp_path / "source/plugins/turbo-mode/ticket",
            now=parts["created_at"] + timedelta(minutes=5),
            execute_surface="direct_execute",
        )


def test_verify_activation_proof_rejects_stale_proof(tmp_path: Path) -> None:
    parts = _base_components(tmp_path)
    proof = build_activation_proof(
        project_root=parts["project_root"],
        run_nonce=parts["run_nonce"],
        created_at=parts["created_at"],
        status="activated",
        installed_cache_root=parts["installed_root"],
        plugin_manifest_path=parts["plugin_manifest"],
        runtime_identity={"codex_version": "codex-cli 0.test"},
        inventory={
            "request_methods": ["initialize", "initialized", "plugin/read", "plugin/list", "skills/list", "hooks/list"],
            "marketplace_path": str(parts["project_root"] / ".agents/plugins/marketplace.json"),
            "remote_marketplace_name": None,
            "cwd": str(parts["project_root"]),
            "transcript_sha256": "inventory-sha",
            "plugin_read_source_path": str(parts["source_root"]),
            "plugin_read_source_sha256": "plugin-read-sha",
            "installed_runtime_root": str(parts["installed_root"]),
            "installed_runtime_root_evidence": "hooks/list.sourcePath",
            "ticket_skill_names": ["ticket:ticket-capture", "ticket:ticket-update", "ticket:ticket-find", "ticket:ticket-review", "ticket:ticket-doctor"],
            "ticket_skill_paths": [
                str(parts["installed_root"] / "skills/ticket-capture/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-update/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-find/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-review/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-doctor/SKILL.md"),
            ],
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "source_path": str(parts["hook_manifest"]),
                "hook_manifest_path": str(parts["hook_manifest"]),
                "hook_manifest_sha256": "hook-manifest-sha",
                "guard_command": f"python3 {parts['guard_script']}",
                "guard_script_path": str(parts["guard_script"]),
                "guard_script_sha256": "guard-sha",
            },
        },
        smoke={
            "runner": "app_server_turn",
            "status": "passed",
            "turn_status": "completed",
            "raw_hook_events_sha256": "events-sha",
            "payload_sha256_before": "payload-before-sha",
            "payload_sha256_after": "payload-after-sha",
            "smoke_project_root": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "cwd": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "autonomy_config_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/.codex/ticket.local.md",
            "autonomy_config": {"mode": "auto_audit", "max_creates": 3, "warnings": []},
            "command": "python3 installed execute payload",
            "payload_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "tickets_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets",
            "payload_tickets_dir": "docs/tickets",
            "hook_request_origin": "user",
            "hook_injected": True,
            "session_id": "host-session",
            "nonce": parts["run_nonce"],
            "engine_state": "ok_create",
            "ticket_id": "T-20260520-01",
        },
        raw_evidence={
            "run_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
            "app_server_transcript": "raw/app-server-transcript.jsonl",
        },
    )

    with pytest.raises(RuntimeReadinessError, match="expired"):
        _verify_activation_bootstrap_base_proof_for_execute(
            proof,
            project_root=parts["project_root"],
            executing_plugin_root=parts["installed_root"],
            now=parts["created_at"] + timedelta(hours=25),
            execute_surface="direct_execute",
        )


def test_verify_activation_proof_rejects_missing_raw_evidence(tmp_path: Path) -> None:
    parts = _base_components(tmp_path)
    proof = build_activation_proof(
        project_root=parts["project_root"],
        run_nonce=parts["run_nonce"],
        created_at=parts["created_at"],
        status="activated",
        installed_cache_root=parts["installed_root"],
        plugin_manifest_path=parts["plugin_manifest"],
        runtime_identity={"codex_version": "codex-cli 0.test", "executable_path": "/usr/bin/codex", "executable_sha256": None, "executable_hash_unavailable_reason": "test"},
        inventory={
            "request_methods": ["initialize", "initialized", "plugin/read", "plugin/list", "skills/list", "hooks/list"],
            "marketplace_path": str(parts["project_root"] / ".agents/plugins/marketplace.json"),
            "remote_marketplace_name": None,
            "cwd": str(parts["project_root"]),
            "transcript_sha256": "missing-transcript",
            "plugin_read_source_path": str(parts["source_root"]),
            "plugin_read_source_sha256": "plugin-read-sha",
            "installed_runtime_root": str(parts["installed_root"]),
            "installed_runtime_root_evidence": "hooks/list.sourcePath",
            "ticket_skill_names": ["ticket:ticket-capture", "ticket:ticket-update", "ticket:ticket-find", "ticket:ticket-review", "ticket:ticket-doctor"],
            "ticket_skill_paths": [
                str(parts["installed_root"] / "skills/ticket-capture/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-update/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-find/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-review/SKILL.md"),
                str(parts["installed_root"] / "skills/ticket-doctor/SKILL.md"),
            ],
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "source_path": str(parts["hook_manifest"]),
                "hook_manifest_path": str(parts["hook_manifest"]),
                "hook_manifest_sha256": "hook-manifest-sha",
                "guard_command": f"python3 {parts['guard_script']}",
                "guard_script_path": str(parts["guard_script"]),
                "guard_script_sha256": "guard-sha",
            },
        },
        smoke={
            "runner": "app_server_turn",
            "status": "passed",
            "turn_status": "completed",
            "raw_hook_events_sha256": "missing-events",
            "payload_sha256_before": "payload-before-sha",
            "payload_sha256_after": "payload-after-sha",
            "smoke_project_root": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "cwd": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "autonomy_config_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/.codex/ticket.local.md",
            "autonomy_config": {"mode": "auto_audit", "max_creates": 3, "warnings": []},
            "command": f"python3 -B {parts['installed_root']}/scripts/ticket_engine_activation_smoke.py execute {parts['project_root']}/.codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "payload_path": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/payload.json",
            "tickets_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}/docs/tickets",
            "payload_tickets_dir": "docs/tickets",
            "hook_request_origin": "user",
            "hook_injected": True,
            "session_id": "host-session",
            "nonce": parts["run_nonce"],
            "engine_state": "ok_create",
            "ticket_id": "T-20260520-01",
        },
        raw_evidence={
            "run_dir": f".codex/ticket-runtime-smoke/{parts['run_nonce']}",
            "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
            "app_server_transcript": "raw/app-server-transcript.jsonl",
            "hook_membrane_events": "raw/hook-membrane-events.jsonl",
            "agentcontrol_events": "raw/agentcontrol-events.jsonl",
            "smoke_autonomy_config": ".codex/ticket.local.md",
            "payload_before": "raw/payload-before.json",
            "payload_after": "raw/payload-after.json",
            "agentcontrol_payload_after": "raw/agentcontrol-payload-after.json",
            "engine_stdout": "raw/engine-stdout.json",
            "engine_stderr": "raw/engine-stderr.txt",
        },
    )

    with pytest.raises(RuntimeReadinessError, match="raw evidence"):
        _verify_activation_bootstrap_base_proof_for_execute(
            proof,
            project_root=parts["project_root"],
            executing_plugin_root=parts["installed_root"],
            now=parts["created_at"] + timedelta(minutes=5),
            execute_surface="direct_execute",
        )
```

Also add verifier tests that prove raw evidence is parsed semantically, not only
hashed:

- a proof whose `raw/app-server-inventory-transcript.jsonl` hash matches but whose
  `plugin/read` source path differs from `inventory.plugin_read_source_path`
  fails.
- a proof whose `plugin_read_source_sha256` differs from the normalized
  `plugin/read` summary in the raw transcript fails.
- a proof whose `raw/hook-membrane-events.jsonl` lacks the installed Ticket
  schema-shaped `hook/completed` event correlated to the exact smoke
  `commandExecution` turn fails.
- a proof whose `raw/agentcontrol-events.jsonl` lacks the AgentControl child
  thread/turn correlation fails.
- a fixture/direct-hook transcript with no app-server `initialize`,
  id-less `initialized`, `plugin/read`, `plugin/list`, `skills/list`,
  `hooks/list`, `thread/start`, and `turn/start` semantics fails even if the
  file hashes match the proof. If `inventory.request_methods` claims
  `initialized` but the raw transcript omits the notification, the verifier
  must reject the proof.
- a proof whose matching Ticket `hook/completed` notification has
  `run.status!="completed"` or contains an unsupported hook-output warning,
  including the observed unsupported `permissionDecision: allow` warning, fails
  even when payload injection and command execution appear to succeed.
- a proof whose normalized hook rows contain `command`, `payloadPath`, or
  `nonce` fields that are not backed by raw `commandExecution`, payload bytes,
  and same-turn `hook/completed` records fails.
- a proof whose raw command is equivalent except for one canonical `-B` flag
  passes command-identity comparison, while noncanonical shapes such as
  `python3 -BB ...` fail.
- a proof whose normalized `engine_state` says `ok_create` but whose
  `raw/engine-stdout.json` is missing, has a mismatched hash, parses to a
  non-`ok_create` state, omits the nonce, or names a different ticket id fails.
- a proof whose `raw/engine-stdout.json` omits both top-level `ticket_path` and
  `engine_response.data.ticket_path`, or whose raw ticket path differs from
  `hook_membrane_smoke.ticket_path`, fails before checking the ticket file.
- a proof whose engine stdout says `ok_create` but whose created ticket file or
  `.audit/YYYY-MM-DD/<session_id>.jsonl` artifact is missing, outside the smoke
  tickets dir, hash-mismatched, or lacks `attempt_started` plus `create` /
  `ok_create` audit rows fails.
- a proof whose smoke project lacks `.codex/ticket.local.md`, whose live config
  parses as `suggest`, or whose execute payload omits/mismatches
  `autonomy_config` fails with `policy_blocked` and writes no proof.
- a smoke config that uses `max_creates` instead of the live
  `max_creates_per_session` frontmatter key fails a non-default cap assertion
  when parsed through `read_autonomy_config()`.
- a proof whose smoke turn contains extra `commandExecution` items in the same
  turn fails closed.
- activation child-process environment sanitization unsets or ignores ambient
  `CODEX_PLUGIN_ROOT`; a malicious inherited value pointing at the source
  checkout cannot make production activation or the installed hook resolve the
  executing plugin root from that environment variable.
- an app-server smoke whose pinned `workspaceWrite` sandbox fails with the
  current `sandbox-exec: sandbox_apply: Operation not permitted` diagnostic
  records a policy failure and writes no proof; the source suite must not
  convert that failure into a `dangerFullAccess` activation pass.
- a proof whose installed-code hash set omits any installed `scripts/*.py` file
  fails. This includes top-level entrypoints and helper modules on mutation,
  containment, trust, validation, parsing, rendering, dedup, and payload paths.
- a proof whose installed-code hash for any expected path differs from the
  current installed cache file fails; include explicit helper drift cases for
  `ticket_paths.py` and `ticket_trust.py`.
- a proof with `status="activation_in_progress"` fails normal
  `verify_activation_closeout_proof_for_execute()` even if all raw evidence
  otherwise matches. Candidate status can only be accepted by the dedicated
  post-smoke verifier for contained smoke paths.
- a fully valid bootstrap/base proof is accepted by
  `_verify_activation_bootstrap_base_proof_for_execute()` so missing imports
  such as `normalize_app_server_jsonrpc_transcript` fail before negative
  verifier cases mask them; a normal activated proof is accepted only by
  `verify_activation_closeout_proof_for_execute()` with matching
  `post_activation_gated_smokes` for the requested surface.
- unknown `execute_surface` raises `RuntimeReadinessError`; ingest bypass must
  be tested at the caller before this verifier is invoked.
- a proof whose activation scope says `capture_execute` or `update_execute` is
  gated but whose `post_activation_gated_smokes.surface_results` lacks that
  surface fails both activation closeout and normal `engine_execute()` for that
  surface.
- a proof whose `capture_execute` or `update_execute` post-smoke evidence lacks
  a successful hook-mediated `prepare` command, or whose wrapper
  `session_id` / `hook_injected` / `hook_request_origin` trust inputs differ
  between prepare and execute, fails activation closeout.
- a capture/update post-smoke whose wrapper returns `stale_plan` before the
  readiness gate is classified as a wrapper trust-fingerprint setup failure, not
  as passing or failing runtime readiness proof.
- a bootstrap-only proof whose hook membrane smoke passes but whose actual
  post-proof `ticket_engine_agent.py execute` smoke is missing or failed is not
  an activation success and is rejected by the normal execute gate.
- a malicious normal execute payload under a path shaped like
  `.codex/ticket-runtime-smoke/<nonce>/post-direct/` but targeting the proof
  project's real `docs/tickets` cannot use `.codex/ticket-runtime-proof.candidate.json`
  to mutate target tickets; candidate mode must require the exact
  command/payload/tickets-dir/proof-root tuple and contained post-smoke tickets
  dir.
- a proof that uses `excluded_execute_surfaces` or names `"ingest"` /
  `"activation_smoke"` as public execute surfaces fails schema validation; the
  proof must use `excluded_mutation_paths` with `ingest_dispatch` and
  `activation_smoke_bootstrap`.

- [ ] **Step 2: Run the new tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py tests/test_hook.py tests/test_execute.py -q
```

Expected: FAIL because `scripts.ticket_runtime_readiness` does not exist.

- [ ] **Step 3: Add the runtime readiness module skeleton**

Create `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

PROOF_SCHEMA_VERSION = "installed-ticket-runtime-readiness-v1"
PARSER_VERSION = "installed-ticket-runtime-readiness-1"
ACCEPTED_RESPONSE_SCHEMA_VERSION = "ticket-app-server-readonly-inventory-v1"
TICKET_PLUGIN_ID = "ticket@turbo-mode"
TICKET_PLUGIN_NAME = "ticket"
TICKET_PLUGIN_VERSION = "1.4.0"
ACTIVATED_STATUS = "activated"
ACTIVATION_IN_PROGRESS_STATUS = "activation_in_progress"
ACTIVATION_FAILED_STATUS = "activation_failed"
PROOF_RELATIVE_PATH = Path(".codex/ticket-runtime-proof.json")
CANDIDATE_PROOF_RELATIVE_PATH = Path(".codex/ticket-runtime-proof.candidate.json")
SMOKE_RELATIVE_ROOT = Path(".codex/ticket-runtime-smoke")
PROOF_MAX_AGE = timedelta(hours=24)
ACTIVATING_EXECUTE_SURFACES = ("direct_execute", "capture_execute", "update_execute")
EXCLUDED_MUTATION_PATHS = ("ingest_dispatch", "activation_smoke_bootstrap")
POST_SMOKE_DIRECTORIES = {
    "direct_execute": "post-direct",
    "capture_execute": "post-capture",
    "update_execute": "post-update",
}
POST_SMOKE_PAYLOAD_FILENAMES = {
    "direct_execute": "post-direct-payload.json",
    "capture_execute": "post-capture-payload.json",
    "update_execute": "post-update-payload.json",
}
POST_SMOKE_EXECUTE_SCRIPTS = {
    "direct_execute": "ticket_engine_agent.py",
    "capture_execute": "ticket_capture_agent.py",
    "update_execute": "ticket_update_agent.py",
}
REQUIRED_INSTALLED_CODE_PATHS = {
    "scripts/__init__.py",
    "scripts/ticket_audit.py",
    "scripts/ticket_capture.py",
    "scripts/ticket_capture_agent.py",
    "scripts/ticket_dedup.py",
    "scripts/ticket_doctor.py",
    "scripts/ticket_engine_activation_smoke.py",
    "scripts/ticket_engine_agent.py",
    "scripts/ticket_engine_core.py",
    "scripts/ticket_engine_runner.py",
    "scripts/ticket_engine_user.py",
    "scripts/ticket_envelope.py",
    "scripts/ticket_id.py",
    "scripts/ticket_parse.py",
    "scripts/ticket_paths.py",
    "scripts/ticket_payloads.py",
    "scripts/ticket_read.py",
    "scripts/ticket_render.py",
    "scripts/ticket_review.py",
    "scripts/ticket_stage_models.py",
    "scripts/ticket_runtime_readiness.py",
    "scripts/ticket_triage.py",
    "scripts/ticket_trust.py",
    "scripts/ticket_update.py",
    "scripts/ticket_update_agent.py",
    "scripts/ticket_ux.py",
    "scripts/ticket_validate.py",
    "scripts/ticket_workflow.py",
}


class RuntimeReadinessError(ValueError):
    """Raised when runtime readiness evidence cannot activate execution."""


def proof_path_for_project(project_root: Path) -> Path:
    """Return the project-local final activation proof path."""
    return project_root / PROOF_RELATIVE_PATH


def candidate_proof_path_for_project(project_root: Path) -> Path:
    """Return the non-authorizing activation closeout candidate path."""
    return project_root / CANDIDATE_PROOF_RELATIVE_PATH


def post_smoke_candidate_context_for_payload(
    *,
    execute_surface: str,
    payload_path: Path | None,
) -> tuple[Path, str] | None:
    """Return proof target root and nonce for exact activation post-smoke payloads."""
    if payload_path is None or execute_surface not in ACTIVATING_EXECUTE_SURFACES:
        return None
    resolved = payload_path.resolve()
    parts = resolved.parts
    marker = (".codex", "ticket-runtime-smoke")
    marker_index: int | None = None
    for index in range(len(parts) - len(marker)):
        if parts[index : index + len(marker)] == marker:
            marker_index = index
            break
    if marker_index is None:
        return None
    proof_target_project_root = Path(*parts[:marker_index])
    smoke_parts = parts[marker_index + len(marker) :]
    if len(smoke_parts) != 3:
        return None
    run_nonce, post_dir, payload_name = smoke_parts
    if post_dir != POST_SMOKE_DIRECTORIES[execute_surface]:
        return None
    if payload_name != POST_SMOKE_PAYLOAD_FILENAMES[execute_surface]:
        return None
    return proof_target_project_root.resolve(), run_nonce


def ticket_command_identity(command: str) -> tuple[str, str, str] | None:
    """Normalize canonical Ticket Bash command identity for proof comparison."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or tokens[0] != "python3":
        return None
    index = 1
    if index < len(tokens) and tokens[index] == "-B":
        index += 1
    if len(tokens) != index + 3:
        return None
    script_path = Path(tokens[index]).resolve()
    subcommand = tokens[index + 1]
    payload_path = Path(tokens[index + 2]).resolve()
    return str(script_path), subcommand, str(payload_path)


def load_activation_proof(project_root: Path) -> dict[str, Any]:
    """Load the project-local final activation proof or fail closed."""
    path = proof_path_for_project(project_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeReadinessError(
            f"runtime proof load failed: proof file not found. Got: {str(path)!r:.100}"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeReadinessError(
            f"runtime proof load failed: {exc}. Got: {str(path)!r:.100}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeReadinessError(
            f"runtime proof load failed: proof is not an object. Got: {type(payload).__name__!r:.100}"
        )
    return payload


def load_activation_candidate_proof(project_root: Path) -> dict[str, Any]:
    """Load the non-authorizing closeout candidate proof or fail closed."""
    path = candidate_proof_path_for_project(project_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeReadinessError(
            f"runtime candidate proof load failed: proof is not an object. Got: {type(payload).__name__!r:.100}"
        )
    return payload


def new_run_nonce(now: datetime | None = None) -> str:
    """Return a nonce used to bind inventory, smoke, and proof."""
    active_now = now or datetime.now(UTC)
    stamp = active_now.strftime("%Y%m%dT%H%M%SZ")
    return f"ticket-runtime-{stamp}-{secrets.token_hex(8)}"


def sha256_regular_file(path: Path) -> str:
    """Hash a regular file or fail with a stable activation error."""
    if not path.is_file():
        raise RuntimeReadinessError(f"sha256 file failed: path is not a file. Got: {str(path)!r:.100}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_installed_code_paths(installed_cache_root: Path) -> tuple[str, ...]:
    """Return the full installed Ticket scripts closure to bind into proof."""
    scripts_root = installed_cache_root / "scripts"
    paths = tuple(
        sorted(
            path.relative_to(installed_cache_root).as_posix()
            for path in scripts_root.glob("*.py")
            if path.is_file()
        )
    )
    missing = sorted(REQUIRED_INSTALLED_CODE_PATHS.difference(paths))
    if missing:
        raise RuntimeReadinessError(f"installed code identity failed: missing required scripts. Got: {missing!r:.100}")
    return paths


def collect_installed_code_identity(installed_cache_root: Path) -> dict[str, Any]:
    """Hash every installed Ticket script, including helper modules on write paths."""
    expected_paths = expected_installed_code_paths(installed_cache_root)
    return {
        "hash_algorithm": "sha256",
        "paths": {
            rel_path: sha256_regular_file(installed_cache_root / rel_path)
            for rel_path in expected_paths
        },
    }


def build_activation_proof(
    *,
    project_root: Path,
    run_nonce: str,
    created_at: datetime,
    installed_cache_root: Path,
    plugin_manifest_path: Path,
    runtime_identity: dict[str, Any],
    inventory: dict[str, Any],
    smoke: dict[str, Any],
    raw_evidence: dict[str, Any],
    agentcontrol_hook_traversal_smoke: dict[str, Any] | None = None,
    status: str = ACTIVATION_IN_PROGRESS_STATUS,
) -> dict[str, Any]:
    """Build the normalized activation proof payload."""
    if status not in {ACTIVATION_IN_PROGRESS_STATUS, ACTIVATED_STATUS}:
        raise RuntimeReadinessError(f"proof build failed: unsupported status. Got: {status!r:.100}")
    expires_at = created_at + PROOF_MAX_AGE
    return {
        "schema_version": PROOF_SCHEMA_VERSION,
        "status": status,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "run_nonce": run_nonce,
        "project_root": str(project_root),
        "ticket_plugin": {
            "plugin_id": TICKET_PLUGIN_ID,
            "name": TICKET_PLUGIN_NAME,
            "version": TICKET_PLUGIN_VERSION,
            "installed_cache_root": str(installed_cache_root),
            "plugin_manifest_path": str(plugin_manifest_path),
            "plugin_manifest_sha256": sha256_regular_file(plugin_manifest_path),
        },
        "installed_code_identity": collect_installed_code_identity(installed_cache_root),
        "runtime_identity": {
            **runtime_identity,
            "accepted_response_schema_version": ACCEPTED_RESPONSE_SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
        },
        "app_server_transcript_sha256": sha256_regular_file(
            project_root / str(raw_evidence["run_dir"]) / str(raw_evidence["app_server_transcript"])
        ),
        "inventory": inventory,
        "hook_membrane_smoke": smoke,
        "agentcontrol_hook_traversal_smoke": agentcontrol_hook_traversal_smoke or {},
        "activation_scope": {
            "gated_execute_surfaces": list(ACTIVATING_EXECUTE_SURFACES),
            "excluded_mutation_paths": list(EXCLUDED_MUTATION_PATHS),
            "request_origin": "agent",
            "hook_request_origin_contract": "metadata_only_currently_user",
            "autonomy_mode": "auto_audit",
        },
        "raw_evidence": raw_evidence,
    }


def _parse_utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeReadinessError(f"{field} failed: expected non-empty UTC timestamp. Got: {value!r:.100}")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise RuntimeReadinessError(f"{field} failed: timestamp must include timezone. Got: {value!r:.100}")
    return parsed.astimezone(UTC)


def _verify_installed_code_identity(value: object, installed_cache_root: Path) -> None:
    if not isinstance(value, dict):
        raise RuntimeReadinessError("runtime proof failed: missing installed code identity")
    if value.get("hash_algorithm") != "sha256":
        raise RuntimeReadinessError("runtime proof failed: installed code hash algorithm mismatch")
    paths = value.get("paths")
    expected_paths = expected_installed_code_paths(installed_cache_root)
    if not isinstance(paths, dict) or set(paths) != set(expected_paths):
        raise RuntimeReadinessError("runtime proof failed: installed code path set mismatch")
    for rel_path in expected_paths:
        expected = sha256_regular_file(installed_cache_root / rel_path)
        if paths.get(rel_path) != expected:
            raise RuntimeReadinessError(
                f"runtime proof failed: installed code hash mismatch. Got: {rel_path!r:.100}"
            )


def _verify_activation_bootstrap_base_proof_for_execute(
    proof: dict[str, Any],
    *,
    project_root: Path,
    executing_plugin_root: Path,
    now: datetime | None = None,
    execute_surface: str,
) -> None:
    """Private bootstrap/base verifier; does not verify post-proof gated smokes."""
    if execute_surface not in ACTIVATING_EXECUTE_SURFACES:
        raise RuntimeReadinessError(f"runtime proof failed: unsupported execute surface. Got: {execute_surface!r:.100}")
    active_now = now or datetime.now(UTC)
    resolved_project = project_root.resolve()
    resolved_plugin = executing_plugin_root.resolve()
    if proof.get("schema_version") != PROOF_SCHEMA_VERSION:
        raise RuntimeReadinessError("runtime proof failed: unsupported schema")
    if proof.get("status") != ACTIVATED_STATUS:
        raise RuntimeReadinessError("runtime proof failed: status is not activated")
    if proof.get("project_root") != str(resolved_project):
        raise RuntimeReadinessError("runtime proof failed: project root mismatch")
    expires_at = _parse_utc(proof.get("expires_at"), field="expires_at")
    if active_now > expires_at:
        raise RuntimeReadinessError("runtime proof failed: proof expired")
    ticket_plugin = proof.get("ticket_plugin")
    if not isinstance(ticket_plugin, dict):
        raise RuntimeReadinessError("runtime proof failed: missing ticket_plugin")
    installed_root = ticket_plugin.get("installed_cache_root")
    if installed_root != str(resolved_plugin):
        raise RuntimeReadinessError("runtime proof failed: executing plugin root does not match installed proof root")
    plugin_manifest = resolved_plugin / ".codex-plugin/plugin.json"
    if ticket_plugin.get("plugin_manifest_path") != str(plugin_manifest):
        raise RuntimeReadinessError("runtime proof failed: plugin manifest path mismatch")
    if ticket_plugin.get("plugin_manifest_sha256") != sha256_regular_file(plugin_manifest):
        raise RuntimeReadinessError("runtime proof failed: plugin manifest hash mismatch")
    _verify_installed_code_identity(proof.get("installed_code_identity"), resolved_plugin)
    inventory = proof.get("inventory")
    if not isinstance(inventory, dict):
        raise RuntimeReadinessError("runtime proof failed: missing inventory")
    if inventory.get("cwd") != str(resolved_project):
        raise RuntimeReadinessError("runtime proof failed: inventory cwd mismatch")
    if inventory.get("installed_runtime_root") != str(resolved_plugin):
        raise RuntimeReadinessError("runtime proof failed: inventory installed runtime root mismatch")
    if inventory.get("installed_runtime_root_evidence") != "hooks/list.sourcePath":
        raise RuntimeReadinessError("runtime proof failed: installed runtime root evidence mismatch")
    expected_skills = {
        "ticket:ticket-capture",
        "ticket:ticket-update",
        "ticket:ticket-find",
        "ticket:ticket-review",
        "ticket:ticket-doctor",
    }
    if set(inventory.get("ticket_skill_names", [])) != expected_skills:
        raise RuntimeReadinessError("runtime proof failed: Ticket skill inventory mismatch")
    skill_paths = inventory.get("ticket_skill_paths")
    if not isinstance(skill_paths, list) or len(skill_paths) != len(expected_skills):
        raise RuntimeReadinessError("runtime proof failed: Ticket skill path inventory mismatch")
    for skill_path in skill_paths:
        path = Path(skill_path).resolve()
        try:
            path.relative_to(resolved_plugin / "skills")
        except ValueError as exc:
            raise RuntimeReadinessError(
                f"runtime proof failed: Ticket skill path not under installed cache. Got: {skill_path!r:.100}"
            ) from exc
    hook = inventory.get("hook")
    if not isinstance(hook, dict):
        raise RuntimeReadinessError("runtime proof failed: missing hook identity")
    hook_manifest = resolved_plugin / "hooks/hooks.json"
    guard_script = resolved_plugin / "hooks/ticket_engine_guard.py"
    if hook.get("hook_manifest_path") != str(hook_manifest):
        raise RuntimeReadinessError("runtime proof failed: hook manifest path mismatch")
    if hook.get("hook_manifest_sha256") != sha256_regular_file(hook_manifest):
        raise RuntimeReadinessError("runtime proof failed: hook manifest hash mismatch")
    if hook.get("guard_command") != f"python3 {guard_script}":
        raise RuntimeReadinessError("runtime proof failed: guard command mismatch")
    if hook.get("guard_script_path") != str(guard_script):
        raise RuntimeReadinessError("runtime proof failed: guard script path mismatch")
    if hook.get("guard_script_sha256") != sha256_regular_file(guard_script):
        raise RuntimeReadinessError("runtime proof failed: guard script hash mismatch")
    smoke = proof.get("hook_membrane_smoke")
    if not isinstance(smoke, dict):
        raise RuntimeReadinessError("runtime proof failed: missing hook membrane smoke")
    if smoke.get("runner") != "app_server_turn" or smoke.get("status") != "passed":
        raise RuntimeReadinessError("runtime proof failed: live app-server hook membrane smoke did not pass")
    smoke_project_root = resolved_project / SMOKE_RELATIVE_ROOT / str(proof.get("run_nonce"))
    smoke_project_rel = f"{SMOKE_RELATIVE_ROOT.as_posix()}/{proof.get('run_nonce')}"
    if smoke.get("smoke_project_root") != smoke_project_rel or smoke.get("cwd") != smoke_project_rel:
        raise RuntimeReadinessError("runtime proof failed: smoke project root mismatch")
    if smoke.get("autonomy_config_path") != f"{smoke_project_rel}/.codex/ticket.local.md":
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy config path mismatch")
    autonomy_config = smoke.get("autonomy_config")
    if not isinstance(autonomy_config, dict) or autonomy_config.get("mode") != "auto_audit":
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy config mismatch")
    payload_path = smoke_project_root / "payload.json"
    expected_command = f"python3 -B {resolved_plugin}/scripts/ticket_engine_activation_smoke.py execute {payload_path}"
    if ticket_command_identity(str(smoke.get("command", ""))) != ticket_command_identity(expected_command):
        raise RuntimeReadinessError("runtime proof failed: smoke command mismatch")
    if smoke.get("hook_request_origin") != "user" or smoke.get("hook_injected") is not True:
        raise RuntimeReadinessError("runtime proof failed: smoke did not prove current hook membrane provenance")
    if not isinstance(smoke.get("session_id"), str) or not smoke["session_id"]:
        raise RuntimeReadinessError("runtime proof failed: smoke session_id missing")
    if smoke.get("engine_state") != "ok_create":
        raise RuntimeReadinessError("runtime proof failed: smoke engine state mismatch")
    if smoke.get("nonce") != proof.get("run_nonce"):
        raise RuntimeReadinessError("runtime proof failed: smoke nonce mismatch")
    raw = proof.get("raw_evidence")
    if not isinstance(raw, dict):
        raise RuntimeReadinessError("runtime proof failed: missing raw evidence")
    run_dir = _contained_relative_path(resolved_project, raw.get("run_dir"), must_be_dir=True)
    inventory_transcript = _contained_run_path(run_dir, raw.get("app_server_inventory_transcript"))
    app_server_transcript = _contained_run_path(run_dir, raw.get("app_server_transcript"))
    hook_membrane_events = _contained_run_path(run_dir, raw.get("hook_membrane_events"))
    smoke_autonomy_config = _contained_run_path(run_dir, raw.get("smoke_autonomy_config"))
    _verify_smoke_autonomy_config(smoke_autonomy_config, smoke.get("autonomy_config"))
    if inventory.get("transcript_sha256") != sha256_regular_file(inventory_transcript):
        raise RuntimeReadinessError("runtime proof failed: inventory transcript hash mismatch")
    if proof.get("app_server_transcript_sha256") != sha256_regular_file(app_server_transcript):
        raise RuntimeReadinessError("runtime proof failed: aggregate app-server transcript hash mismatch")
    inventory_records = _load_jsonl_artifact(inventory_transcript)
    _verify_inventory_transcript_matches_proof(
        inventory_records,
        inventory=inventory,
        project_root=resolved_project,
    )
    transcript_records = _load_jsonl_artifact(app_server_transcript)
    normalized_transcript_events = normalize_app_server_jsonrpc_transcript(transcript_records)
    _verify_app_server_smoke_transcript_matches_proof(
        normalized_transcript_events,
        expected_command=expected_command,
        expected_cwd=smoke_project_root,
        run_nonce=str(proof.get("run_nonce")),
    )
    if smoke.get("raw_hook_events_sha256") != sha256_regular_file(hook_membrane_events):
        raise RuntimeReadinessError("runtime proof failed: hook membrane event hash mismatch")
    hook_event_records = _load_jsonl_artifact(hook_membrane_events)
    _verify_event_rows_derived_from_raw(hook_event_records, normalized_transcript_events)
    _verify_hook_membrane_events_match_proof(
        hook_event_records,
        hook=hook,
        smoke=smoke,
        expected_command=expected_command,
        expected_cwd=smoke_project_root,
        payload_path=payload_path,
        run_nonce=str(proof.get("run_nonce")),
    )
    payload_before = _contained_run_path(run_dir, raw.get("payload_before"))
    payload_after = _contained_run_path(run_dir, raw.get("payload_after"))
    if smoke.get("payload_sha256_before") != sha256_regular_file(payload_before):
        raise RuntimeReadinessError("runtime proof failed: smoke payload-before hash mismatch")
    if smoke.get("payload_sha256_after") != sha256_regular_file(payload_after):
        raise RuntimeReadinessError("runtime proof failed: smoke payload-after hash mismatch")
    engine_stdout = _contained_run_path(run_dir, raw.get("engine_stdout"))
    if smoke.get("engine_stdout_sha256") != sha256_regular_file(engine_stdout):
        raise RuntimeReadinessError("runtime proof failed: smoke engine stdout hash mismatch")
    engine_result = _load_json_artifact(engine_stdout)
    _verify_engine_result_matches_smoke(
        engine_result,
        smoke=smoke,
        project_root=resolved_project,
        payload_path=payload_path,
        smoke_tickets_dir=smoke_project_root / "docs/tickets",
        run_nonce=str(proof.get("run_nonce")),
    )
    _verify_smoke_ticket_and_audit_artifacts(
        smoke=smoke,
        project_root=resolved_project,
        smoke_tickets_dir=smoke_project_root / "docs/tickets",
        session_id=str(smoke["session_id"]),
    )
    traversal = proof.get("agentcontrol_hook_traversal_smoke")
    if not isinstance(traversal, dict) or traversal.get("status") != "passed":
        raise RuntimeReadinessError("runtime proof failed: missing AgentControl hook traversal smoke")
    if traversal.get("hook_request_origin") != "user" or traversal.get("hook_injected") is not True:
        raise RuntimeReadinessError("runtime proof failed: AgentControl smoke did not traverse current hook membrane")
    agentcontrol_events = _contained_run_path(run_dir, raw.get("agentcontrol_events"))
    if traversal.get("raw_hook_events_sha256") != sha256_regular_file(agentcontrol_events):
        raise RuntimeReadinessError("runtime proof failed: AgentControl hook event hash mismatch")
    agent_payload_after = _contained_run_path(run_dir, raw.get("agentcontrol_payload_after"))
    if traversal.get("payload_sha256_after") != sha256_regular_file(agent_payload_after):
        raise RuntimeReadinessError("runtime proof failed: AgentControl payload hash mismatch")
    if traversal.get("smoke_project_root") != smoke_project_rel or traversal.get("cwd") != smoke_project_rel:
        raise RuntimeReadinessError("runtime proof failed: AgentControl smoke project root mismatch")
    agent_payload_path = smoke_project_root / "agentcontrol-payload.json"
    expected_agent_command = f"python3 -B {resolved_plugin}/scripts/ticket_engine_activation_smoke.py execute {agent_payload_path}"
    if ticket_command_identity(str(traversal.get("command", ""))) != ticket_command_identity(expected_agent_command):
        raise RuntimeReadinessError("runtime proof failed: AgentControl smoke command mismatch")
    agent_event_records = _load_jsonl_artifact(agentcontrol_events)
    _verify_event_rows_derived_from_raw(agent_event_records, normalized_transcript_events)
    _verify_agentcontrol_events_match_proof(
        agent_event_records,
        hook=hook,
        traversal=traversal,
        expected_command=expected_agent_command,
        expected_cwd=smoke_project_root,
        payload_path=agent_payload_path,
        run_nonce=str(proof.get("run_nonce")),
    )
    if traversal.get("installed_hook_source_path") != str(hook_manifest):
        raise RuntimeReadinessError("runtime proof failed: AgentControl hook source mismatch")
    if traversal.get("nonce") != proof.get("run_nonce"):
        raise RuntimeReadinessError("runtime proof failed: AgentControl smoke nonce mismatch")
    for field in ("parent_thread_id", "child_thread_id", "child_turn_id"):
        if not isinstance(traversal.get(field), str) or not traversal[field]:
            raise RuntimeReadinessError(f"runtime proof failed: AgentControl {field} missing")
    runtime_identity = proof.get("runtime_identity")
    if not isinstance(runtime_identity, dict):
        raise RuntimeReadinessError("runtime proof failed: missing runtime identity")
    _verify_codex_identity(runtime_identity)


def verify_activation_candidate_for_post_smoke(
    proof: dict[str, Any],
    *,
    project_root: Path,
    executing_plugin_root: Path,
    now: datetime | None = None,
    run_nonce: str,
    execute_surface: str,
    command: str,
    payload_path: Path,
    tickets_dir: Path,
) -> None:
    """Accept an in-progress candidate only for contained post-smoke executes."""
    if proof.get("status") != ACTIVATION_IN_PROGRESS_STATUS:
        raise RuntimeReadinessError("runtime candidate proof failed: status is not activation_in_progress")
    if execute_surface not in ACTIVATING_EXECUTE_SURFACES:
        raise RuntimeReadinessError(f"runtime candidate proof failed: unsupported surface. Got: {execute_surface!r:.100}")
    if proof.get("run_nonce") != run_nonce:
        raise RuntimeReadinessError("runtime candidate proof failed: nonce mismatch")
    expected_root = project_root / SMOKE_RELATIVE_ROOT / run_nonce / POST_SMOKE_DIRECTORIES[execute_surface]
    expected_payload_path = (expected_root / POST_SMOKE_PAYLOAD_FILENAMES[execute_surface]).resolve()
    expected_tickets_dir = (expected_root / "docs/tickets").resolve()
    expected_command = (
        f"python3 {executing_plugin_root.resolve() / 'scripts' / POST_SMOKE_EXECUTE_SCRIPTS[execute_surface]} "
        f"execute {expected_payload_path}"
    )
    expected_identity = ticket_command_identity(expected_command)
    if ticket_command_identity(command) != expected_identity:
        raise RuntimeReadinessError("runtime candidate proof failed: command does not match contained post-smoke command")
    if payload_path.resolve() != expected_payload_path:
        raise RuntimeReadinessError("runtime candidate proof failed: payload path is not the exact post-smoke payload")
    if tickets_dir.resolve() != expected_tickets_dir:
        raise RuntimeReadinessError("runtime candidate proof failed: tickets dir is not the contained post-smoke dir")
    activated_view = dict(proof)
    activated_view["status"] = ACTIVATED_STATUS
    _verify_activation_bootstrap_base_proof_for_execute(
        activated_view,
        project_root=project_root,
        executing_plugin_root=executing_plugin_root,
        now=now,
        execute_surface=execute_surface,
    )


def verify_activation_closeout_proof_for_execute(
    proof: dict[str, Any],
    *,
    project_root: Path,
    executing_plugin_root: Path,
    now: datetime | None = None,
    execute_surface: str,
) -> None:
    """Verify the normal gate proof plus post-proof evidence for one surface."""
    _verify_activation_bootstrap_base_proof_for_execute(
        proof,
        project_root=project_root,
        executing_plugin_root=executing_plugin_root,
        now=now,
        execute_surface=execute_surface,
    )
    post_smokes = proof.get("post_activation_gated_smokes")
    if not isinstance(post_smokes, dict) or post_smokes.get("status") != "passed":
        raise RuntimeReadinessError("runtime proof closeout failed: missing post-proof gated smokes")
    _verify_post_activation_gated_smoke_for_surface(
        proof,
        execute_surface=execute_surface,
        project_root=project_root,
        executing_plugin_root=executing_plugin_root,
    )


def verify_activation_closeout_proof(
    proof: dict[str, Any],
    *,
    project_root: Path,
    executing_plugin_root: Path,
    now: datetime | None = None,
) -> None:
    """Verify full activation closeout for every gated surface."""
    for execute_surface in _proof_gated_execute_surfaces(proof):
        verify_activation_closeout_proof_for_execute(
            proof,
            project_root=project_root,
            executing_plugin_root=executing_plugin_root,
            now=now,
            execute_surface=execute_surface,
        )
    _verify_post_activation_gated_smokes(proof, project_root=project_root, executing_plugin_root=executing_plugin_root)


def _contained_relative_path(project_root: Path, raw_value: object, *, must_be_dir: bool) -> Path:
    if not isinstance(raw_value, str) or raw_value.startswith("/"):
        raise RuntimeReadinessError(f"raw evidence path failed: expected relative path. Got: {raw_value!r:.100}")
    path = (project_root / raw_value).resolve()
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeReadinessError(f"raw evidence path failed: escaped project root. Got: {raw_value!r:.100}") from exc
    if must_be_dir and not path.is_dir():
        raise RuntimeReadinessError(f"raw evidence path failed: directory missing. Got: {str(path)!r:.100}")
    if not must_be_dir and not path.is_file():
        raise RuntimeReadinessError(f"raw evidence path failed: file missing. Got: {str(path)!r:.100}")
    return path


def _contained_run_path(run_dir: Path, raw_value: object) -> Path:
    if not isinstance(raw_value, str) or raw_value.startswith("/"):
        raise RuntimeReadinessError(f"raw evidence path failed: expected run-relative path. Got: {raw_value!r:.100}")
    path = (run_dir / raw_value).resolve()
    try:
        path.relative_to(run_dir)
    except ValueError as exc:
        raise RuntimeReadinessError(f"raw evidence path failed: escaped run directory. Got: {raw_value!r:.100}") from exc
    if not path.is_file():
        raise RuntimeReadinessError(f"raw evidence path failed: file missing. Got: {str(path)!r:.100}")
    return path


def _load_jsonl_artifact(path: Path) -> list[dict[str, Any]]:
    """Load compact JSONL evidence and reject non-object rows."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeReadinessError(f"raw evidence parse failed: expected object row. Got: {value!r:.100}")
        rows.append(value)
    if not rows:
        raise RuntimeReadinessError(f"raw evidence parse failed: empty artifact. Got: {str(path)!r:.100}")
    return rows


def _load_json_artifact(path: Path) -> dict[str, Any]:
    """Load a JSON evidence object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeReadinessError(f"raw evidence parse failed: expected object. Got: {value!r:.100}")
    return value


def normalize_app_server_jsonrpc_transcript(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive schema-shaped event rows from raw direction/body JSON-RPC rows."""
    normalized: list[dict[str, Any]] = []
    for row in records:
        if row.get("direction") not in {"send", "recv"} or not isinstance(row.get("body"), dict):
            raise RuntimeReadinessError("runtime proof failed: malformed raw app-server transcript row")
        body = row["body"]
        method = body.get("method")
        if not isinstance(method, str):
            continue
        params = body.get("params", {})
        if not isinstance(params, dict):
            raise RuntimeReadinessError("runtime proof failed: malformed app-server notification params")
        event = {"method": method}
        event.update(params)
        normalized.append(event)
    return normalized


def _verify_event_rows_derived_from_raw(
    event_rows: list[dict[str, Any]],
    normalized_transcript_events: list[dict[str, Any]],
) -> None:
    """Reject event artifacts that are not exact rows derived from raw JSON-RPC."""
    remaining = list(normalized_transcript_events)
    for row in event_rows:
        try:
            index = remaining.index(row)
        except ValueError as exc:
            raise RuntimeReadinessError("runtime proof failed: normalized event row is not raw-backed") from exc
        remaining.pop(index)


def _verify_smoke_autonomy_config(path: Path, snapshot: object) -> None:
    """Verify the disposable smoke project config with the live parser."""
    from scripts.ticket_engine_core import read_autonomy_config

    tickets_dir = path.parent.parent / "docs/tickets"
    config = read_autonomy_config(tickets_dir)
    if config.mode != "auto_audit":
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy config is not auto_audit")
    if not isinstance(snapshot, dict) or snapshot.get("mode") != "auto_audit":
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy snapshot mismatch")
    if snapshot.get("max_creates") != config.max_creates or config.max_creates != 3:
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy cap mismatch")
    if list(snapshot.get("warnings", [])) != list(config.warnings):
        raise RuntimeReadinessError("runtime proof failed: smoke autonomy warnings mismatch")


def _verify_engine_result_matches_smoke(
    result: dict[str, Any],
    *,
    smoke: dict[str, Any],
    project_root: Path,
    payload_path: Path,
    smoke_tickets_dir: Path,
    run_nonce: str,
) -> None:
    """Re-parse raw engine stdout and bind it to the normalized smoke."""
    if result.get("state") != "ok_create" or smoke.get("engine_state") != result.get("state"):
        raise RuntimeReadinessError("runtime proof failed: raw engine result state mismatch")
    if result.get("ticket_id") != smoke.get("ticket_id"):
        raise RuntimeReadinessError("runtime proof failed: raw engine ticket id mismatch")
    if result.get("nonce") != run_nonce:
        raise RuntimeReadinessError("runtime proof failed: raw engine nonce mismatch")
    if result.get("payload_path") != str(payload_path):
        raise RuntimeReadinessError("runtime proof failed: raw engine payload path mismatch")
    if result.get("tickets_dir") != str(smoke_tickets_dir):
        raise RuntimeReadinessError("runtime proof failed: raw engine tickets dir mismatch")
    smoke_ticket_path = smoke.get("ticket_path")
    if not isinstance(smoke_ticket_path, str):
        raise RuntimeReadinessError("runtime proof failed: smoke ticket path missing")
    expected_ticket_path = (project_root / smoke_ticket_path).resolve()
    ticket_candidates: list[Path] = []
    raw_ticket_path = result.get("ticket_path")
    if isinstance(raw_ticket_path, str):
        raw_path = Path(raw_ticket_path)
        ticket_candidates.append(raw_path if raw_path.is_absolute() else (project_root / raw_path).resolve())
    engine_response = result.get("engine_response")
    if isinstance(engine_response, dict):
        engine_data = engine_response.get("data")
        if isinstance(engine_data, dict) and isinstance(engine_data.get("ticket_path"), str):
            raw_path = Path(engine_data["ticket_path"])
            ticket_candidates.append(raw_path if raw_path.is_absolute() else (project_root / raw_path).resolve())
    if not ticket_candidates:
        raise RuntimeReadinessError("runtime proof failed: raw engine ticket path missing")
    if expected_ticket_path not in ticket_candidates:
        raise RuntimeReadinessError("runtime proof failed: raw engine ticket path mismatch")
    try:
        expected_ticket_path.relative_to(smoke_tickets_dir)
    except ValueError as exc:
        raise RuntimeReadinessError("runtime proof failed: raw engine ticket path escaped smoke tickets dir") from exc


def _verify_smoke_ticket_and_audit_artifacts(
    *,
    smoke: dict[str, Any],
    project_root: Path,
    smoke_tickets_dir: Path,
    session_id: str,
) -> None:
    """Verify the smoke mutation actually wrote a contained ticket and audit result."""
    ticket_path = _contained_relative_path(project_root, smoke.get("ticket_path"), must_be_dir=False)
    try:
        ticket_path.relative_to(smoke_tickets_dir)
    except ValueError as exc:
        raise RuntimeReadinessError("runtime proof failed: smoke ticket path escaped smoke tickets dir") from exc
    if smoke.get("ticket_sha256") != sha256_regular_file(ticket_path):
        raise RuntimeReadinessError("runtime proof failed: smoke ticket hash mismatch")
    ticket_text = ticket_path.read_text(encoding="utf-8")
    if str(smoke.get("ticket_id")) not in ticket_text:
        raise RuntimeReadinessError("runtime proof failed: smoke ticket does not contain ticket id")

    audit_file = _contained_relative_path(project_root, smoke.get("audit_file_path"), must_be_dir=False)
    try:
        audit_file.relative_to(smoke_tickets_dir / ".audit")
    except ValueError as exc:
        raise RuntimeReadinessError("runtime proof failed: smoke audit path escaped smoke audit dir") from exc
    if smoke.get("audit_file_sha256") != sha256_regular_file(audit_file):
        raise RuntimeReadinessError("runtime proof failed: smoke audit hash mismatch")
    audit_rows = _load_jsonl_artifact(audit_file)
    started = [row for row in audit_rows if row.get("action") == "attempt_started"]
    results = [row for row in audit_rows if row.get("action") == "create" and row.get("result") == "ok_create"]
    if len(started) != 1 or len(results) != 1:
        raise RuntimeReadinessError("runtime proof failed: smoke audit result entries missing")
    for row in (*started, *results):
        if row.get("session_id") != session_id or row.get("request_origin") != "agent":
            raise RuntimeReadinessError("runtime proof failed: smoke audit provenance mismatch")
        if row.get("autonomy_mode") != "auto_audit":
            raise RuntimeReadinessError("runtime proof failed: smoke audit autonomy mismatch")
        if row.get("ticket_id") not in {None, smoke.get("ticket_id")}:
            raise RuntimeReadinessError("runtime proof failed: smoke audit ticket id mismatch")


def _verify_inventory_transcript_matches_proof(
    records: list[dict[str, Any]],
    *,
    inventory: dict[str, Any],
    project_root: Path,
) -> None:
    """Re-parse raw inventory transcript and compare normalized authority fields."""
    normalized = validate_inventory_transcript(
        records,
        project_root=project_root,
        marketplace_path=Path(str(inventory.get("marketplace_path"))),
        remote_marketplace_name=inventory.get("remote_marketplace_name"),
    )
    for field in (
        "plugin_read_source_path",
        "plugin_read_source_sha256",
        "installed_runtime_root",
        "installed_runtime_root_evidence",
        "ticket_skill_names",
        "ticket_skill_paths",
        "hook",
    ):
        if normalized.get(field) != inventory.get(field):
            raise RuntimeReadinessError(f"runtime proof failed: raw inventory {field} mismatch")


def _verify_app_server_smoke_transcript_matches_proof(
    records: list[dict[str, Any]],
    *,
    expected_command: str,
    expected_cwd: Path,
    run_nonce: str,
) -> None:
    """Require normalized raw-backed events to include one smoke command turn."""
    serialized = json.dumps(records, sort_keys=True)
    expected_identity = ticket_command_identity(expected_command)
    for needle in ("initialize", "plugin/read", "skills/list", "hooks/list", "thread/start", "turn/start"):
        if needle not in serialized:
            raise RuntimeReadinessError(f"runtime proof failed: raw app-server transcript missing {needle}")
    command_items = [
        row
        for row in records
        if row.get("method") in {"item/started", "item/completed"}
        and isinstance(row.get("item"), dict)
        and row["item"].get("type") == "commandExecution"
    ]
    matching = [
        row
        for row in command_items
        if ticket_command_identity(str(row["item"].get("command", ""))) == expected_identity
        and row["item"].get("cwd") == str(expected_cwd)
    ]
    matching_ids = {row["item"].get("id") for row in matching}
    if len(matching_ids) != 1:
        raise RuntimeReadinessError("runtime proof failed: expected exactly one smoke commandExecution")
    command_id = next(iter(matching_ids))
    turn_id = matching[0].get("turnId")
    if not isinstance(turn_id, str) or not turn_id:
        raise RuntimeReadinessError("runtime proof failed: smoke commandExecution missing turnId")
    extra_commands = [
        row
        for row in command_items
        if row.get("turnId") == turn_id and row["item"].get("id") != command_id
    ]
    if extra_commands:
        raise RuntimeReadinessError("runtime proof failed: extra commandExecution in smoke turn")
    if run_nonce not in serialized:
        raise RuntimeReadinessError("runtime proof failed: raw app-server smoke nonce mismatch")


def _verify_hook_membrane_events_match_proof(
    records: list[dict[str, Any]],
    *,
    hook: dict[str, Any],
    smoke: dict[str, Any],
    expected_command: str,
    expected_cwd: Path,
    payload_path: Path,
    run_nonce: str,
) -> None:
    """Require schema-shaped raw events to prove command and hook correlation."""
    expected_identity = ticket_command_identity(expected_command)
    command_rows = [
        row
        for row in records
        if row.get("method") in {"item/started", "item/completed"}
        and isinstance(row.get("item"), dict)
        and row["item"].get("type") == "commandExecution"
        and ticket_command_identity(str(row["item"].get("command", ""))) == expected_identity
        and row["item"].get("cwd") == str(expected_cwd)
    ]
    command_ids = {row["item"].get("id") for row in command_rows}
    if len(command_ids) != 1:
        raise RuntimeReadinessError("runtime proof failed: raw smoke commandExecution mismatch")
    thread_id = command_rows[0].get("threadId")
    turn_id = command_rows[0].get("turnId")
    hook_rows = [
        row
        for row in records
        if row.get("method") == "hook/completed"
        and row.get("threadId") == thread_id
        and row.get("turnId") == turn_id
        and isinstance(row.get("run"), dict)
        and row["run"].get("sourcePath") == hook.get("hook_manifest_path")
        and row["run"].get("eventName") == "preToolUse"
        and row["run"].get("status") == "completed"
    ]
    if len(hook_rows) != 1:
        raise RuntimeReadinessError("runtime proof failed: raw hook completion mismatch")
    if _hook_run_has_unsupported_output_warning(hook_rows[0]["run"]):
        raise RuntimeReadinessError("runtime proof failed: unsupported hook output warning")
    if smoke.get("nonce") != run_nonce:
        raise RuntimeReadinessError("runtime proof failed: smoke nonce mismatch")


def _verify_agentcontrol_events_match_proof(
    records: list[dict[str, Any]],
    *,
    hook: dict[str, Any],
    traversal: dict[str, Any],
    expected_command: str,
    expected_cwd: Path,
    payload_path: Path,
    run_nonce: str,
) -> None:
    """Require raw AgentControl items plus child command/hook correlation."""
    expected_identity = ticket_command_identity(expected_command)
    spawn_rows = [
        row
        for row in records
        if row.get("method") in {"item/started", "item/completed"}
        and isinstance(row.get("item"), dict)
        and row["item"].get("type") == "collabAgentToolCall"
        and row["item"].get("tool") == "spawnAgent"
    ]
    if len(spawn_rows) != 1:
        raise RuntimeReadinessError("runtime proof failed: expected exactly one AgentControl spawnAgent item")
    receivers = spawn_rows[0]["item"].get("receiverThreadIds")
    if receivers != [traversal.get("child_thread_id")]:
        raise RuntimeReadinessError("runtime proof failed: AgentControl receiver thread mismatch")
    child_commands = [
        row
        for row in records
        if row.get("threadId") == traversal.get("child_thread_id")
        and row.get("method") in {"item/started", "item/completed"}
        and isinstance(row.get("item"), dict)
        and row["item"].get("type") == "commandExecution"
        and ticket_command_identity(str(row["item"].get("command", ""))) == expected_identity
        and row["item"].get("cwd") == str(expected_cwd)
    ]
    child_command_ids = {row["item"].get("id") for row in child_commands}
    if len(child_command_ids) != 1:
        raise RuntimeReadinessError("runtime proof failed: AgentControl child commandExecution mismatch")
    child_turn_id = child_commands[0].get("turnId")
    child_command_id = next(iter(child_command_ids))
    extra_child_commands = [
        row
        for row in records
        if row.get("threadId") == traversal.get("child_thread_id")
        and row.get("turnId") == child_turn_id
        and row.get("method") in {"item/started", "item/completed"}
        and isinstance(row.get("item"), dict)
        and row["item"].get("type") == "commandExecution"
        and row["item"].get("id") != child_command_id
    ]
    if extra_child_commands:
        raise RuntimeReadinessError("runtime proof failed: extra AgentControl child commandExecution")
    child_hooks = [
        row
        for row in records
        if row.get("method") == "hook/completed"
        and row.get("threadId") == traversal.get("child_thread_id")
        and row.get("turnId") == child_turn_id
        and isinstance(row.get("run"), dict)
        and row["run"].get("sourcePath") == hook.get("hook_manifest_path")
        and row["run"].get("eventName") == "preToolUse"
        and row["run"].get("status") == "completed"
    ]
    if len(child_hooks) != 1:
        raise RuntimeReadinessError("runtime proof failed: raw AgentControl traversal semantics mismatch")
    if _hook_run_has_unsupported_output_warning(child_hooks[0]["run"]):
        raise RuntimeReadinessError("runtime proof failed: unsupported AgentControl hook output warning")


def _hook_run_has_unsupported_output_warning(run: dict[str, Any]) -> bool:
    """Return True when Codex reported the Ticket hook output as unsupported."""
    entries = run.get("entries", [])
    if not isinstance(entries, list):
        return True
    for entry in entries:
        if not isinstance(entry, dict):
            return True
        text = str(entry.get("text", ""))
        if "unsupported" in text.lower() and "permissionDecision" in text:
            return True
    return False


def _verify_codex_identity(runtime_identity: dict[str, Any]) -> None:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeReadinessError("runtime proof failed: codex executable unavailable")
    if runtime_identity.get("executable_path") != executable:
        raise RuntimeReadinessError("runtime proof failed: codex executable path mismatch")
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
    if version.returncode != 0 or version.stdout.strip() != runtime_identity.get("codex_version"):
        raise RuntimeReadinessError("runtime proof failed: codex version mismatch")
    expected_hash = runtime_identity.get("executable_sha256")
    if isinstance(expected_hash, str) and expected_hash:
        if sha256_regular_file(Path(executable)) != expected_hash:
            raise RuntimeReadinessError("runtime proof failed: codex executable hash mismatch")
```

- [ ] **Step 4: Run the schema tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py tests/test_hook.py tests/test_execute.py -q
```

Expected: PASS for the initial schema/validator tests.

- [ ] **Step 5: Commit schema and validator**

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): add runtime readiness proof schema"
```

Expected: commit contains only the new module and tests.

---

### Task 2: Ticket-Owned App-Server Inventory Collector

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing inventory parser tests**

Append tests that build fake app-server transcripts and assert:

- `build_inventory_requests()` emits `plugin/read` and `plugin/list` with the same `marketplacePath` and `remoteMarketplaceName`.
- `build_inventory_requests()` emits `skills/list` and `hooks/list` with `cwds == [str(project_root)]`.
- `plugin/read` source resolves to the repo/source Ticket root and is recorded as marketplace metadata, not installed-runtime proof.
- `plugin/list` shows `ticket@turbo-mode` installed and enabled.
- `skills/list` includes prefixed live names `ticket:ticket-capture`, `ticket:ticket-update`, `ticket:ticket-find`, `ticket:ticket-review`, and `ticket:ticket-doctor`.
- every Ticket skill record has a path under the installed Ticket cache root.
- `hooks/list` has exactly one Ticket hook with `eventName == "preToolUse"`, `matcher == "Bash"`, no warnings/errors, command `python3 <installed_root>/hooks/ticket_engine_guard.py`, and `sourcePath == <installed_root>/hooks/hooks.json`.
- the normalized `installed_runtime_root` is derived from `hooks/list.sourcePath` / guard command and corroborated by the `skills/list` cache paths, not by `plugin/read`.
- duplicate Ticket hooks fail.
- wrong hook command fails.
- missing `plugin/read` response fails.

Use this shape for the happy-path transcript fixture:

```python
def inventory_transcript(installed_root: Path, source_root: Path) -> list[dict[str, object]]:
    return [
        {"direction": "recv", "body": {"id": 0, "result": {
            "serverInfo": {"name": "codex-app-server", "version": "0.test"},
            "capabilities": {"experimentalApi": True},
        }}},
        {"direction": "recv", "body": {"id": 1, "result": {
            "plugin": {"summary": {
                "id": "ticket@turbo-mode",
                "name": "ticket",
                "version": "1.4.0",
                "enabled": True,
                "installed": True,
                "source": {"path": str(source_root)},
            }}
        }}},
        {"direction": "recv", "body": {"id": 2, "result": {
            "plugins": [{"id": "ticket@turbo-mode", "enabled": True, "installed": True}]
        }}},
        {"direction": "recv", "body": {"id": 3, "result": {
            "skills": [
                {"name": "ticket:ticket-capture", "path": f"{installed_root}/skills/ticket-capture/SKILL.md"},
                {"name": "ticket:ticket-update", "path": f"{installed_root}/skills/ticket-update/SKILL.md"},
                {"name": "ticket:ticket-find", "path": f"{installed_root}/skills/ticket-find/SKILL.md"},
                {"name": "ticket:ticket-review", "path": f"{installed_root}/skills/ticket-review/SKILL.md"},
                {"name": "ticket:ticket-doctor", "path": f"{installed_root}/skills/ticket-doctor/SKILL.md"},
            ]
        }}},
        {"direction": "recv", "body": {"id": 4, "result": {
            "data": [{
                "warnings": [],
                "errors": [],
                "hooks": [{
                    "pluginId": "ticket@turbo-mode",
                    "eventName": "preToolUse",
                    "matcher": "Bash",
                    "command": f"python3 {installed_root}/hooks/ticket_engine_guard.py",
                    "sourcePath": f"{installed_root}/hooks/hooks.json",
                }],
            }]
        }}},
    ]
```

The production parser must tolerate documented app-server field variations already handled by local refresh tests, but it must not accept missing or ambiguous evidence.

- [ ] **Step 2: Run parser tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: FAIL because inventory parsing functions are not implemented.

- [ ] **Step 3: Implement inventory request and parser functions**

Add these public functions to `ticket_runtime_readiness.py`:

- `build_inventory_requests(project_root: Path, *, marketplace_path: Path, remote_marketplace_name: str | None) -> list[dict[str, Any]]`
- `collect_app_server_inventory(project_root: Path, *, marketplace_path: Path, remote_marketplace_name: str | None = None, roundtrip: object | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]`
- `validate_inventory_transcript(transcript: list[dict[str, Any]], *, project_root: Path, marketplace_path: Path, remote_marketplace_name: str | None) -> dict[str, Any]`
- `app_server_roundtrip(requests: list[dict[str, Any]], *, cwd: Path) -> list[dict[str, Any]]`
- `collect_codex_runtime_identity() -> dict[str, Any]`

Implementation rules:

- Use `shutil.which("codex")` once per collection and run that exact executable for both `codex --version` and `codex app-server --listen stdio://`.
- Request ids must be stable: `0` initialize, `1` plugin/read Ticket, `2` plugin/list, `3` skills/list, `4` hooks/list.
- `initialized` is sent as a notification after initialize and has no id.
- `plugin/read` request params must be `{"marketplacePath": str(marketplace_path), "pluginName": "ticket", "remoteMarketplaceName": remote_marketplace_name}`.
- `plugin/list` request params must be `{"marketplacePath": str(marketplace_path), "remoteMarketplaceName": remote_marketplace_name}`.
- `skills/list` and `hooks/list` params must be `{"cwds": [str(project_root.resolve())]}`.
- The normalized inventory dict must include `marketplace_path`, `remote_marketplace_name`, and `cwd` exactly as used in requests; the verifier later compares those fields to the project and activation arguments.
- Store `plugin/read` as `plugin_read_source_path` source metadata. Do not derive `installed_runtime_root` from `plugin/read`.
- Compute `plugin_read_source_sha256` from a canonical JSON digest of the normalized `plugin/read` Ticket summary, including at minimum plugin id, name, version, enabled/installed status, and source path. The verifier must recompute this digest from the raw transcript.
- Derive `installed_runtime_root` from the Ticket `hooks/list.sourcePath` and guard command, require both to share the same installed cache root, and require every Ticket skill path from `skills/list` to live under `<installed_runtime_root>/skills/`.
- Preserve live prefixed skill names exactly as returned by app-server: `ticket:ticket-capture`, `ticket:ticket-update`, `ticket:ticket-find`, `ticket:ticket-review`, and `ticket:ticket-doctor`.
- Store raw transcript lines under the smoke run directory only in Task 4; Task 2 returns transcript data to callers.
- Treat response errors, duplicate ids, unexpected ids, missing ids, timeout, malformed JSON, and missing required result fields as `RuntimeReadinessError`.
- Use the same error style as the repo: `"{operation} failed: {reason}. Got: {input!r:.100}"`.

- [ ] **Step 4: Run parser tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit inventory collector**

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): collect activation runtime inventory"
```

Expected: commit contains only runtime-readiness module and tests.

---

### Task 2.5: Hook Output Contract Preflight

**Files:**
- Modify: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing hook output tests**

Add source tests that make the current Codex 0.132 hook-output contract
explicit before any live activation smoke is considered valid:

- canonical allowed Ticket commands return a supported Codex hook output shape
  and do not emit `hookSpecificOutput.permissionDecision="allow"` or
  `permissionDecisionReason`.
- denied Ticket commands continue to fail closed using a Codex-supported block
  shape. If Codex 0.132 does not expose a supported block shape for `PreToolUse`,
  stop and report that Ticket cannot claim activation readiness without a host
  hook contract change.
- the runtime readiness app-server parser rejects any matching Ticket hook run
  whose `run.entries` contain an unsupported-hook-output warning, including the
  observed `permissionDecision: allow` warning.

- [ ] **Step 2: Implement the hook output contract**

Update `_make_allow()` / `_make_deny()` in `ticket_engine_guard.py` only after
checking the current Codex hook contract. The source contract must be:

- allow path: side-effect payload injection plus a supported no-block response;
  do not rely on unsupported `permissionDecision="allow"`.
- deny path: a supported block/stop response that the app-server reports as a
  blocked or stopped hook run, not a warning-only unsupported field.
- app-server warning path: any unsupported hook-output warning makes activation
  fail before proof write.

- [ ] **Step 3: Run hook output tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_hook.py tests/test_runtime_readiness.py -q
```

Expected: PASS for source tests. Installed activation still requires an explicit
post-refresh live run; source tests do not prove the installed cache has this
hook output fix.

- [ ] **Step 4: Commit hook output contract preflight**

```bash
git add plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py plugins/turbo-mode/ticket/tests/test_hook.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "fix(ticket): align hook output with Codex app-server contract"
```

Expected: commit contains only the hook output contract change and tests.

---

### Task 2.6: Production Root Environment Sanitization

**Files:**
- Modify: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing root-override regression tests**

Add source tests that prove production hook and activation execution do not
trust ambient root overrides:

- `ticket_engine_guard.py` ignores or rejects ambient `CODEX_PLUGIN_ROOT` for
  production root discovery; tests that need alternate plugin roots use an
  explicit pytest helper/seam rather than inherited subprocess environment.
- activation app-server child launches use a sanitized environment that removes
  `CODEX_PLUGIN_ROOT`, `PYTHONPATH`, and any fixture variables that could supply
  inventory, smoke, or installed-root evidence.
- a malicious `CODEX_PLUGIN_ROOT` pointing at the source checkout cannot make
  `activate-runtime`, the hook guard, or proof verification accept source-local
  execution as installed-cache execution.

- [ ] **Step 2: Remove or pytest-scope the override**

Update production root discovery so the running plugin root comes from
`Path(__file__).resolve().parents[1]` only. If existing tests need to run the
hook against temp plugin roots, move that behavior behind a pytest-only helper
or direct in-process function argument. Do not leave a production subprocess
path where inherited `CODEX_PLUGIN_ROOT` changes trust decisions.

- [ ] **Step 3: Run root-override tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_hook.py tests/test_runtime_readiness.py -q
```

Expected: PASS. No installed-cache mutation has happened; this only proves the
source hook and activation launcher sanitize root overrides.

- [ ] **Step 4: Commit root environment sanitization**

```bash
git add plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_hook.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "fix(ticket): sanitize activation root environment"
```

Expected: commit contains only production root-discovery/env sanitization and
tests.

---

### Task 3: Live Codex-Mediated Smoke Harness

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing smoke harness tests**

Add tests for:

- smoke workspace path is `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/`.
- smoke workspace is a disposable project root with its own
  `.codex/ticket.local.md` frontmatter setting `autonomy_mode: auto_audit`.
- smoke execute payload includes an `autonomy_config` snapshot matching the
  disposable project's live config.
- activation smoke command uses `ticket_engine_activation_smoke.py execute`, not
  normal `ticket_engine_agent.py execute`, to avoid first-activation deadlock.
- payload starts without `hook_injected`, `hook_request_origin`, or `session_id`.
- fake app-server turn runner that emits JSON rows validated against the
  regenerated 0.132.0 JSON Schema for `ItemCompletedNotification` and
  `HookCompletedNotification`, including `completedAtMs` and required
  `HookRunSummary` fields, with a schema-shaped `commandExecution` item and
  same-turn installed Ticket `hook/completed`, writes injected trust fields,
  and captures engine stdout produces
  `hook_membrane_smoke.status == "passed"`.
- smoke rejects `runner != "app_server_turn"`.
- smoke rejects missing `hook_injected`.
- smoke rejects missing or empty `session_id`.
- smoke rejects `hook_request_origin != "user"` for current Codex 0.132.
- smoke rejects nonce mismatch.
- smoke rejects missing `.codex/ticket.local.md`, `suggest` mode, and missing or
  mismatched payload `autonomy_config`.
- smoke rejects extra `commandExecution` items in the same turn.
- smoke rejects `hook/completed` rows whose `run.entries` contain unsupported
  hook-output warnings.
- activation smoke entrypoint bypasses the runtime proof gate only when
  `cwd`, payload path, and resolved `tickets_dir` are inside the same
  `.codex/ticket-runtime-smoke/<run_nonce>/` run directory.
- activation smoke entrypoint rejects target-project `docs/tickets`, path escape
  attempts, missing nonce, nonce/run-dir mismatch, and any payload-selected
  `execute_surface`.
- ordinary `ticket_engine_agent.py execute` with the same payload still requires
  an existing runtime proof.
- capture/update wrapper execute cannot use the activation bootstrap bypass.
- smoke records and verifies `payload_sha256_before` against `raw/payload-before.json`.
- smoke records and verifies `payload_sha256_after` against `raw/payload-after.json` after hook injection.
- smoke writes, hashes, and parses `raw/engine-stdout.json`; it rejects missing
  engine output, hash mismatch, `state != "ok_create"`, ticket id mismatch,
  nonce mismatch, payload path mismatch, or tickets dir mismatch.
- smoke rejects a run where `engine_stdout` claims success but the created
  ticket file is missing/outside the smoke tickets dir/hash-mismatched, or the
  smoke audit file is missing/outside the smoke tickets dir/hash-mismatched or
  lacks the `attempt_started` and `create` / `ok_create` rows.
- smoke config uses `max_creates_per_session: 3` and is verified by the live
  `read_autonomy_config()` parser so the non-default cap cannot be masked by
  the default value.
- a positive subprocess test invokes the real `ticket_engine_activation_smoke.py
  execute <payload>` entrypoint from the disposable smoke root with a
  hook-injected payload fixture (`hook_injected=true`,
  `hook_request_origin=user`, non-empty `session_id`) and asserts `ok_create`.
  This test must run after the origin-metadata engine change below and must not
  monkeypatch engine success.
- AgentControl child traversal smoke rejects a transcript without a
  schema-shaped `collabAgentToolCall` item where `tool == "spawnAgent"` and
  `receiverThreadIds` has exactly one child thread.
- AgentControl child traversal smoke rejects a child turn without exactly one
  matching `commandExecution` and same-turn installed Ticket `hook/completed`.
- direct hook-script fixture output cannot satisfy smoke validation.

Test with an injected runner instead of launching real Codex:

```python
def test_app_server_hook_membrane_smoke_accepts_hook_injected_payload(
    tmp_path: Path,
) -> None:
    parts = _base_components(tmp_path)
    project_root = parts["project_root"]
    project_root.mkdir(parents=True)
    (project_root / ".git").mkdir()

    def fake_roundtrip(requests: list[dict[str, object]], *, cwd: Path) -> list[dict[str, object]]:
        assert requests[0]["method"] == "initialize"
        assert any(req.get("method") == "thread/start" for req in requests)
        assert any(req.get("method") == "turn/start" for req in requests)
        run_nonce = parts["run_nonce"]
        smoke_root = project_root / ".codex/ticket-runtime-smoke" / run_nonce
        assert cwd == smoke_root
        assert (smoke_root / ".codex/ticket.local.md").is_file()
        payload_path = smoke_root / "payload.json"
        before_path = payload_path.parent / "raw/payload-before.json"
        before_path.parent.mkdir(parents=True, exist_ok=True)
        before_path.write_text(payload_path.read_text(encoding="utf-8"), encoding="utf-8")
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        assert payload["tickets_dir"] == "docs/tickets"
        assert payload["autonomy_config"]["mode"] == "auto_audit"
        assert payload["autonomy_config"]["max_creates"] == 3
        payload.update({
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "host-session",
        })
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        after_path = payload_path.parent / "raw/payload-after.json"
        after_path.write_text(payload_path.read_text(encoding="utf-8"), encoding="utf-8")
        engine_result = {
            "state": "ok_create",
            "ticket_id": "T-20260520-01",
            "nonce": run_nonce,
            "payload_path": str(payload_path),
            "tickets_dir": str(smoke_root / "docs/tickets"),
            "ticket_path": f".codex/ticket-runtime-smoke/{run_nonce}/docs/tickets/2026-05-20-example.md",
            "engine_response": {
                "state": "ok_create",
                "ticket_id": "T-20260520-01",
                "data": {"ticket_path": str(smoke_root / "docs/tickets/2026-05-20-example.md")},
            },
        }
        (payload_path.parent / "raw/engine-stdout.json").write_text(json.dumps(engine_result), encoding="utf-8")
        ticket_file = smoke_root / "docs/tickets/2026-05-20-example.md"
        ticket_file.parent.mkdir(parents=True, exist_ok=True)
        ticket_file.write_text("id: T-20260520-01\n", encoding="utf-8")
        audit_file = smoke_root / "docs/tickets/.audit/2026-05-20/host-session.jsonl"
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        audit_file.write_text(
            '{"action":"attempt_started","session_id":"host-session","request_origin":"agent","autonomy_mode":"auto_audit","ticket_id":null}\n'
            '{"action":"create","result":"ok_create","session_id":"host-session","request_origin":"agent","autonomy_mode":"auto_audit","ticket_id":"T-20260520-01"}\n',
            encoding="utf-8",
        )
        command = f"python3 -B {parts['installed_root']}/scripts/ticket_engine_activation_smoke.py execute {payload_path}"
        completed_at = 1_779_232_800_000
        return [{"direction": "send", "body": request} for request in requests] + [
            {
                "direction": "recv",
                "body": {
                    "method": "item/completed",
                    "params": {
                        "completedAtMs": completed_at,
                        "threadId": "parent-thread",
                        "turnId": "turn-1",
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": command,
                            "cwd": str(smoke_root),
                            "status": "completed",
                            "commandActions": [],
                        },
                    },
                },
            },
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "threadId": "parent-thread",
                        "turnId": "turn-1",
                        "run": {
                            "id": "hook-1",
                            "displayOrder": 0,
                            "sourcePath": str(parts["hook_manifest"]),
                            "eventName": "preToolUse",
                            "executionMode": "sync",
                            "handlerType": "command",
                            "scope": "turn",
                            "startedAt": completed_at - 10,
                            "completedAt": completed_at,
                            "status": "completed",
                            "entries": [],
                        },
                    },
                },
            },
            {"direction": "recv", "body": {"method": "turn/completed", "params": {"threadId": "parent-thread", "turn": {"status": "completed"}}}},
        ]

    smoke = run_hook_membrane_smoke(
        project_root=project_root,
        run_nonce=parts["run_nonce"],
        installed_cache_root=parts["installed_root"],
        roundtrip=fake_roundtrip,
    )

    assert smoke["runner"] == "app_server_turn"
    assert smoke["status"] == "passed"
    assert smoke["hook_injected"] is True
    assert smoke["hook_request_origin"] == "user"
    assert smoke["session_id"] == "host-session"
    assert smoke["nonce"] == parts["run_nonce"]
    assert smoke["cwd"] == f".codex/ticket-runtime-smoke/{parts['run_nonce']}"
    assert smoke["autonomy_config"]["mode"] == "auto_audit"
    assert smoke["payload_sha256_before"] == sha256_regular_file(project_root / ".codex/ticket-runtime-smoke" / parts["run_nonce"] / "raw/payload-before.json")
    assert smoke["payload_sha256_after"] == sha256_regular_file(project_root / ".codex/ticket-runtime-smoke" / parts["run_nonce"] / "raw/payload-after.json")
```

- [ ] **Step 2: Run smoke tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: FAIL because `run_hook_membrane_smoke` and `run_agentcontrol_hook_traversal_smoke` are not implemented.

- [ ] **Step 3: Implement app-server hook membrane smokes**

Implementation contract:

- Before adding the positive activation-smoke path, update the existing
  transport-layer trust check in `engine_execute()` so it no longer rejects
  `hook_request_origin != request_origin`. It must still require
  `hook_injected`, a present `hook_request_origin`, and a non-empty
  `session_id`, but the hook-observed origin is metadata only. This ordering is
  required because the activation smoke deliberately sets
  `request_origin="agent"` while current Codex 0.132 hook metadata remains
  `hook_request_origin="user"`.
- Replace the existing origin-mismatch expectations that encode the old model:
  `tests/test_entrypoints.py::test_agent_entrypoint_rejects_hook_user_origin`,
  `tests/test_execute.py::test_user_execute_with_mismatched_hook_origin_rejected`,
  and `tests/test_execute.py::test_agent_execute_with_mismatched_hook_origin_rejected`.
  New tests must assert that hook-origin mismatch is recorded as metadata,
  while missing `hook_injected`, missing `hook_request_origin`, empty
  `session_id`, and unknown entrypoint-selected `request_origin` still fail
  closed.
- Add `ticket_engine_activation_smoke.py` as a tiny installed entrypoint with no
  general-purpose CLI. It accepts only `execute <payload_path>`, sets
  `request_origin="agent"`, forces `execute_surface="activation_smoke"`, and
  calls `engine_execute(..., runtime_readiness_required=False)` only after all
  activation-smoke containment checks pass. It must not read
  `execute_surface`, `runtime_readiness_required`, plugin roots, or policy
  origin from the payload or environment.
- Add the minimal `engine_execute()` keyword parameters needed by that entrypoint
  now: `execute_surface: str = "direct_execute"` and
  `runtime_readiness_required: bool = True`. Before Task 5, these parameters are
  pass-through/no-op except for test assertions. Task 5 later wires external
  surface propagation and the actual readiness gate.
- The activation smoke entrypoint must validate that `Path.cwd()` is exactly the
  smoke project root, the payload path is under that root, the payload nonce
  identifies the same run directory, `tickets_dir` resolves to
  `<smoke_project_root>/docs/tickets`, and the target project's normal
  `docs/tickets` is not the mutation destination. Any failure returns
  `policy_blocked` before mutation.
- Update `ticket_engine_guard.py` to allow exactly
  `python3 [-B] <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_activation_smoke.py execute <PAYLOAD>`
  through the same hook mutation membrane. Do not add wildcard acceptance for
  arbitrary `ticket_engine_*.py` scripts.
- Create run directory with mode `0700`.
- Create raw directory with mode `0700`.
- Treat the run directory itself as a disposable project root for smoke
  execution. Create `<run_dir>/.codex/ticket.local.md` with YAML frontmatter:

```yaml
---
autonomy_mode: auto_audit
max_creates_per_session: 3
---
```

- Create smoke tickets dir at `.codex/ticket-runtime-smoke/<run_nonce>/docs/tickets`.
- Create payload at `.codex/ticket-runtime-smoke/<run_nonce>/payload.json`.
- The payload must include `action=create`, required fields, `tickets_dir="docs/tickets"` relative to the disposable smoke project root, `classify_intent=create`, `classify_confidence=0.95`, `dedup_fingerprint`, `autonomy_config={"mode": "auto_audit", "max_creates": 3, "warnings": []}`, `ticket_runtime_readiness_nonce`, and an internal `activation_result_path="raw/engine-stdout.json"` field. The smoke config must use the live file key `max_creates_per_session: 3`; the payload snapshot keeps the `AutonomyConfig` model field name `max_creates`.
- Before launching the app-server turn, copy the initial payload bytes to `raw/payload-before.json` and record `payload_sha256_before`.
- Use `codex app-server --listen stdio://` with stable JSON-RPC ids. The activation-gate smoke starts a normal app-server thread with `cwd` set to the disposable smoke project root and sends one `turn/start` asking the agent to run exactly this Bash command:
- The app-server client must pin turn policy from the regenerated 0.132.0 schema:
  `thread/start` and `turn/start` set `approvalPolicy="never"`, omit or null
  `approvalsReviewer`, set `cwd` to the absolute disposable smoke project root,
  and set `runtimeWorkspaceRoots=[str(smoke_project_root)]`. `turn/start` must
  also set `sandboxPolicy={"type": "workspaceWrite", "writableRoots":
  [str(smoke_project_root)], "networkAccess": false}`. If the runtime rejects
  that exact sandbox policy shape, activation fails with a schema/policy
  diagnostic instead of silently falling back to operator-dependent defaults.
- The app-server client must fail the smoke if the transcript contains any
  server request with method `item/commandExecution/requestApproval`,
  `item/fileChange/requestApproval`, or `item/permissions/requestApproval`.
  Record the first approval request's method, command, cwd, and available
  decisions in the failure marker, but do not auto-approve, wait for user input,
  or mutate approval policy mid-run.
- Both smoke functions should accept optional `transcript_sink: Path | None = None`; when provided, append their raw app-server send/receive rows to the complete aggregate transcript after the inventory rows. The inventory-only transcript remains a separate file and must never be hash-compared to the aggregate file after these appends.

```text
Run exactly this Bash command once and then stop:
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_activation_smoke.py execute <PAYLOAD_PATH>

Do not run any other shell commands. Do not edit files except through that command.
After the command finishes, answer with exactly: done
```

- Capture the complete app-server transcript as `raw/app-server-transcript.jsonl`,
  after first writing the inventory-only transcript to
  `raw/app-server-inventory-transcript.jsonl`. Both files must use raw
  JSON-RPC send/receive rows: `{"direction": "send"|"recv", "body": ...}`.
- Derive schema-shaped event rows from that raw transcript and write only the
  smoke-relevant subset to `raw/hook-membrane-events.jsonl`. This normalized
  file must contain the host `commandExecution` item(s) and `hook/completed`
  notification(s) derived from app-server notification `params`. Do not
  synthesize `command`, `payloadPath`, or `nonce` fields onto hook notification
  rows. The verifier must recompute the normalized rows from
  `raw/app-server-transcript.jsonl`, prove each row in
  `raw/hook-membrane-events.jsonl` is raw-backed, derive command identity from
  the `commandExecution` item, derive payload/nonce identity from the command
  string and payload bytes, and correlate the installed hook by same
  `threadId`/`turnId`.
- Reject the smoke if the same turn contains zero command executions, more than one command execution, a command different from the expected canonical command, a command `cwd` different from the disposable smoke project root, zero or multiple matching installed Ticket `hook/completed` notifications, or any matching hook `run.entries` warning that reports unsupported hook output such as `permissionDecision`.
- `ticket_engine_activation_smoke.py` must containment-check `activation_result_path`, call `engine_execute()`, then write `raw/engine-stdout.json` itself with a normalized object containing `state`, `ticket_id`, `nonce`, absolute `payload_path`, absolute `tickets_dir`, top-level normalized `ticket_path`, and the raw engine response including `engine_response.data.ticket_path` when present. It should also print the same JSON to stdout. The verifier must hash and parse this artifact, require the raw ticket path to match `hook_membrane_smoke.ticket_path`, and must not trust `hook_membrane_smoke.engine_state` or `hook_membrane_smoke.ticket_path` alone.
- After the run, read the payload file, copy the hook-mutated payload bytes to `raw/payload-after.json`, require `hook_injected is True`, `hook_request_origin == "user"` for current Codex 0.132, and a non-empty `session_id`, then record `payload_sha256_after`.
- Require parsed engine result `state == "ok_create"`, `ticket_id` matching the normalized smoke, nonce matching `run_nonce`, and `tickets_dir` equal to the disposable smoke tickets dir.
- Verify the engine result's top-level `ticket_path` or nested `engine_response.data.ticket_path` matches `hook_membrane_smoke.ticket_path`, exists under the disposable smoke tickets dir, record `ticket_path` and `ticket_sha256`, and verify the `.audit/YYYY-MM-DD/<session_id>.jsonl` file under that same tickets dir contains exactly one `attempt_started` row and one `create` / `ok_create` row for the smoke session before recording `audit_file_path` and `audit_file_sha256`.
- Require the nonce in payload/result to match `run_nonce`.
- Return a normalized `hook_membrane_smoke` dict matching the schema above.
- Then run `run_agentcontrol_hook_traversal_smoke()` in the same run directory. It must start a parent app-server thread, prompt the model to use AgentControl to spawn exactly one child agent, and fail closed if no `collabAgentToolCall` item with `tool == "spawnAgent"` appears. The child prompt must instruct the child to run exactly the same canonical Bash command once from the disposable smoke project root. The harness must wait for child completion only after observing the spawn item and its single `receiverThreadIds` child thread.
- AgentControl traversal must use explicit timeouts and failure classes instead
  of waiting indefinitely or silently retrying. Use separate bounded waits for
  parent spawn observation, child command observation, child hook completion, and
  child turn completion. Classify failures as `agentcontrol_tool_unavailable`,
  `agentcontrol_spawn_timeout`, `agentcontrol_child_command_timeout`,
  `agentcontrol_child_hook_timeout`, `agentcontrol_child_completion_timeout`,
  `agentcontrol_extra_spawn`, or `agentcontrol_extra_command`. Do not perform an
  automatic retry inside the same activation run; operators may rerun
  `activate-runtime`, producing a new nonce and diagnostics.
- The AgentControl payload must use a distinct contained
  `activation_result_path` such as `raw/agentcontrol-engine-stdout.json` so it
  cannot overwrite the primary `raw/engine-stdout.json` success artifact.
- Capture AgentControl traversal as normalized, raw-backed app-server event rows
  in `raw/agentcontrol-events.jsonl`: the parent `collabAgentToolCall` item for
  `spawnAgent`, the child `commandExecution` item, the child same-turn installed
  Ticket `hook/completed` notification, and the child turn completion. Do not
  synthesize command/payload fields onto hook rows; derive them from the child
  command item and payload bytes, and require every normalized row to be
  reproducible from `raw/app-server-transcript.jsonl`.
- AgentControl traversal must reject tool-unavailable cases, missing spawn items, more than one spawn item, empty or multi-entry `receiverThreadIds`, extra child command executions, missing child hook completion, unsupported hook-output warnings, or child thread/turn mismatches.
- Copy the AgentControl hook-mutated payload bytes to `raw/agentcontrol-payload-after.json` and record `payload_sha256_after` in `agentcontrol_hook_traversal_smoke`.
- AgentControl traversal smoke must accept `hook_request_origin == "user"` for current Codex 0.132. If a future Codex release emits a host-owned agent identity field in hook stdin, stop and revise this contract before using it.

- [ ] **Step 4: Run smoke harness tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit live smoke harness**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_execute.py
git commit -m "feat(ticket): add Codex-mediated activation smoke"
```

Expected: commit contains only runtime readiness module, activation smoke
entrypoint, hook allowlist update, and focused tests.

---

### Task 3.5: Same-Thread Session Stability Preflight

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add a narrow app-server preflight helper**

Add a helper that runs before capture/update post-smoke implementation and
proves the installed hook preserves prepare-to-execute trust inputs across two
hook-mediated turns in the same app-server thread. The helper must use a
disposable project root under `.codex/ticket-runtime-smoke/<run_nonce>/preflight/`
or a caller-supplied temp root, never the target project's normal
`docs/tickets/`.

Required preflight shape:

- start one app-server thread with pinned `approvalPolicy="never"`,
  contained `cwd`, explicit runtime workspace roots, and the same workspace-write
  sandbox policy required for activation smokes.
- turn 1 runs exactly `ticket_capture_agent.py prepare <PAYLOAD>` or the
  narrowest equivalent capture wrapper prepare command that traverses the
  installed Ticket hook.
- turn 2 in the same app-server thread runs exactly
  `ticket_capture_agent.py execute <PAYLOAD>`.
- after turn 1, record prepared payload trust inputs:
  `session_id`, `hook_injected`, `hook_request_origin`, contained `tickets_dir`,
  payload path, and saved `execute_fingerprint`.
- after turn 2, verify those same trust inputs are unchanged before accepting
  `state=="ok_create"`.
- record raw transcript rows and normalized event rows, but do not promote or
  write activation proof from this preflight.

- [ ] **Step 2: Encode the live 2026-05-20 findings as expectations**

The current narrow live preflight found:

- `workspaceWrite` against a disposable temp root reached the installed hook but
  failed command execution with `sandbox-exec: sandbox_apply: Operation not
  permitted`.
- `dangerFullAccess` against a disposable temp root proved same-thread
  `session_id` stability for prepare and execute. Both turns used
  `session_id=019e46ff-d846-7f10-99f3-fa0315fe96b8`,
  `hook_injected=true`, `hook_request_origin=user`, `ready_to_execute` prepare,
  unchanged execute fingerprint
  `b0f8c193e145db07656ef61737eb9cbe8d74077f5a1d789e7f46508ac3038369`, and
  `ok_create` execute.
- the same run also observed installed hook completion status `failed` with
  `PreToolUse hook returned unsupported permissionDecision: allow`; that warning
  remains an activation blocker even though payload injection and command
  execution succeeded.

Use this as diagnostic evidence only. The implementation must still require the
workspace-write policy for activation and must fail with a policy diagnostic if
that sandbox shape cannot run on the current host.

- [ ] **Step 3: Add preflight tests**

Add tests that prove:

- same-thread stable trust inputs pass.
- changed `session_id`, `hook_injected`, `hook_request_origin`,
  `tickets_dir`, payload path, or saved `execute_fingerprint` fail before
  post-smoke success is recorded.
- a hook-completed run with `status="failed"` or unsupported
  `permissionDecision` warning fails even if command execution succeeds.
- a workspace-write sandbox launch failure records an environment/policy
  diagnostic and writes no candidate or final proof.

- [ ] **Step 4: Run preflight tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit same-thread preflight**

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "test(ticket): preflight app-server session stability"
```

Expected: commit contains only the preflight helper/tests. This commit does not
claim installed activation readiness.

---

### Task 4: Activation Proof Candidate And Doctor Command Skeleton

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_doctor.py`

- [ ] **Step 1: Add failing proof writer tests**

Add tests proving:

- `_build_activation_proof_candidate()` returns a candidate proof only when
  inventory and bootstrap smokes both pass, but does not write
  `.codex/ticket-runtime-proof.json`.
- inventory-only activation writes no proof.
- smoke-only activation writes no proof.
- operator-supplied fixture transcript activation writes no proof, and
  `ticket_doctor.py activate-runtime` has no environment-variable or CLI fixture
  escape hatch for non-live inventory or smoke collaborators.
- source checkout running plugin root writes no proof.
- caller-supplied plugin root is impossible: activation derives `running_plugin_root()` from the installed module file and has no `--plugin-root` activation argument.
- `marketplace_path`, `remote_marketplace_name`, and `project_root` are passed into inventory collection and preserved in normalized proof.
- proof write is atomic and creates parent `.codex/` with `0700` when needed.
- post-proof gated smoke failure atomically replaces the proof with
  `status="activation_failed"` and the engine gate rejects that marker.
- production activation writes the bootstrap candidate to
  `.codex/ticket-runtime-proof.candidate.json`, never to the final proof path,
  until all post-proof gated smokes pass.
- raw evidence is written under the run directory, not inside the proof JSON.
- activation creates the disposable smoke project `.codex/ticket.local.md`
  before either smoke runner starts and never touches the target project's
  `.codex/ticket.local.md`.
- production `activate_runtime_readiness()` has no injected collector/runner
  parameters; collaborator injection exists only on the private candidate
  builder and test-only doctor handler seam.

- [ ] **Step 2: Add failing doctor CLI tests**

Add `test_ticket_doctor_activate_runtime_writes_proof_only_on_success` against a
test-only command handler, not the production subprocess environment. Refactor
the doctor command into a small internal handler such as
`_handle_activate_runtime(args, *, activation_func=activate_runtime_readiness)`.
Production `main()` must call it without exposing the `activation_func` seam.
The test may call the handler in-process with an injected activation function
that returns a proof object; it must not rely on an environment variable or
fixture path honored by installed `ticket_doctor.py`.

Add a separate subprocess negative test proving the production CLI does not
honor non-live fixtures. Set `TICKET_RUNTIME_READINESS_TEST_FIXTURE=<fixture-json>`
and run:

```python
completed = subprocess.run(
    [
        sys.executable,
        str(DOCTOR_SCRIPT),
        "activate-runtime",
        str(tickets_dir),
        "--marketplace-path",
        str(project_root / ".agents/plugins/marketplace.json"),
    ],
    text=True,
    capture_output=True,
    check=False,
)
```

For the in-process handler success test, expected response shape:

```python
response = _handle_activate_runtime(args, activation_func=fake_activation_success)
assert response["state"] == "ok"
assert response["data"]["mode"] == "activate-runtime"
assert response["data"]["proof"]["status"] == "activated"
assert response["data"]["proof_path"].endswith(".codex/ticket-runtime-proof.json")
```

For the subprocess negative test with `TICKET_RUNTIME_READINESS_TEST_FIXTURE`
set, assert the fixture is ignored: no proof file is written, the response is
not a fixture-driven `"ok"`, and any failure comes from the live activation path
or source-checkout installed-root mismatch rather than from fixture data.

Also add tests that `diagnose --runtime-probe-output` still reports runtime diagnostics but cannot write `.codex/ticket-runtime-proof.json`.

- [ ] **Step 3: Run tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py tests/test_doctor.py -q
```

Expected: FAIL because the candidate builder and doctor skeleton are missing.

- [ ] **Step 4: Implement activation candidate builder**

Add a test-only candidate builder and a fail-closed production placeholder to
`ticket_runtime_readiness.py`. The candidate builder may accept injected
collaborators for direct in-process tests, but it must not write
`.codex/ticket-runtime-proof.json`. The production placeholder must not accept
injected inventory or smoke collaborators and must reject activation until Task
5 wires the real post-proof gated smokes.

```python
def _build_activation_proof_candidate(
    *,
    project_root: Path,
    marketplace_path: Path,
    remote_marketplace_name: str | None = None,
    now: datetime | None = None,
    inventory_collector: Any | None = None,
    smoke_runner: Any | None = None,
    agentcontrol_smoke_runner: Any | None = None,
) -> dict[str, Any]:
    """Build a candidate proof from supplied collectors without writing it."""
    active_now = now or datetime.now(UTC)
    run_nonce = new_run_nonce(active_now)
    executing_plugin_root = running_plugin_root()
    run_root = project_root / SMOKE_RELATIVE_ROOT / run_nonce
    raw_root = run_root / "raw"
    smoke_codex_root = run_root / ".codex"
    run_root.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)
    smoke_codex_root.mkdir(parents=True, exist_ok=True)
    os.chmod(run_root, 0o700)
    os.chmod(raw_root, 0o700)
    write_smoke_autonomy_config(smoke_codex_root / "ticket.local.md")
    collector = inventory_collector or collect_app_server_inventory
    inventory, transcript = collector(
        project_root,
        marketplace_path=marketplace_path,
        remote_marketplace_name=remote_marketplace_name,
    )
    write_jsonl_artifact(raw_root / "app-server-inventory-transcript.jsonl", transcript)
    write_jsonl_artifact(raw_root / "app-server-transcript.jsonl", transcript)
    installed_root = Path(inventory["installed_runtime_root"]).resolve()
    if executing_plugin_root.resolve() != installed_root:
        raise RuntimeReadinessError(
            "activation failed: executing plugin root does not match installed runtime root. "
            f"Got: {str(executing_plugin_root)!r:.100}"
        )
    runner = smoke_runner or run_hook_membrane_smoke
    agent_runner = agentcontrol_smoke_runner or run_agentcontrol_hook_traversal_smoke
    smoke = runner(
        project_root=project_root,
        run_nonce=run_nonce,
        installed_cache_root=installed_root,
        transcript_sink=raw_root / "app-server-transcript.jsonl",
    )
    agentcontrol_smoke = agent_runner(
        project_root=project_root,
        run_nonce=run_nonce,
        installed_cache_root=installed_root,
        transcript_sink=raw_root / "app-server-transcript.jsonl",
    )
    proof = build_activation_proof(
        project_root=project_root.resolve(),
        run_nonce=run_nonce,
        created_at=active_now,
        installed_cache_root=installed_root,
        plugin_manifest_path=installed_root / ".codex-plugin/plugin.json",
        runtime_identity=inventory["runtime_identity"],
        inventory=inventory,
        smoke=smoke,
        agentcontrol_hook_traversal_smoke=agentcontrol_smoke,
        raw_evidence={
            "run_dir": str((SMOKE_RELATIVE_ROOT / run_nonce).as_posix()),
            "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
            "app_server_transcript": "raw/app-server-transcript.jsonl",
            "hook_membrane_events": "raw/hook-membrane-events.jsonl",
            "agentcontrol_events": "raw/agentcontrol-events.jsonl",
            "post_activation_events": "raw/post-activation-gated-events.jsonl",
            "smoke_autonomy_config": ".codex/ticket.local.md",
            "payload_before": "raw/payload-before.json",
            "payload_after": "raw/payload-after.json",
            "agentcontrol_payload_after": "raw/agentcontrol-payload-after.json",
            "engine_stdout": "raw/engine-stdout.json",
            "engine_stderr": "raw/engine-stderr.txt",
        },
    )
    candidate_check = dict(proof)
    candidate_check["status"] = ACTIVATED_STATUS
    _verify_activation_bootstrap_base_proof_for_execute(
        candidate_check,
        project_root=project_root.resolve(),
        executing_plugin_root=executing_plugin_root.resolve(),
        now=active_now,
        execute_surface="direct_execute",
    )
    return proof


def activate_runtime_readiness(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Production activation is completed in Task 5 after the gate exists."""
    raise RuntimeReadinessError(
        "activation failed: post-proof gated smokes are not wired yet. Got: 'task4'"
    )
```

Do not add subprocess fixture plumbing to `ticket_doctor.py activate-runtime`.
Non-live success tests must use direct in-process calls to
`_build_activation_proof_candidate()` or the internal doctor handler with an
injected activation function that returns an already-built proof object. The
installed CLI path must ignore environment variables that try to supply
inventory or smoke fixtures. Task 5 replaces the placeholder
`activate_runtime_readiness()` with the live proof writer after the normal
engine gate and post-proof gated smokes exist.

Add:

```python
def running_plugin_root() -> Path:
    """Return the plugin root for the currently executing Ticket script tree."""
    return Path(__file__).resolve().parents[1]
```

Then implement `write_activation_proof_atomic(project_root: Path, proof: dict[str, Any]) -> Path` using a temp file in `.codex/`, `fsync`, and `os.replace`.
Also implement `write_activation_candidate_atomic(project_root: Path, proof: dict[str, Any]) -> Path` for `.codex/ticket-runtime-proof.candidate.json`; it must require `status="activation_in_progress"` and the normal gate must not load it as final proof.
Also implement `write_activation_failure_marker_atomic(project_root: Path, proof: dict[str, Any]) -> Path` to atomically write the final proof path with `status="activation_failed"` plus the same `run_nonce` when post-proof gated smokes fail. The engine gate must reject that status, so a failed closeout cannot leave an apparently activated proof behind.

Also implement `write_jsonl_artifact(path: Path, rows: list[dict[str, Any]], *, append: bool = False) -> None` for local-only raw evidence. It must create the parent directory with `0700`, write or append one compact JSON object per line, set the artifact mode to `0600`, and reject paths outside the active run directory when called from activation.

- [ ] **Step 5: Wire `ticket_doctor.py activate-runtime`**

Add a new subparser:

```python
activate_p = subparsers.add_parser("activate-runtime")
activate_p.add_argument("tickets_dir", type=Path)
activate_p.add_argument("--marketplace-path", type=Path, required=True)
activate_p.add_argument("--remote-marketplace-name", type=str, default=None)
```

Update `_resolve_tickets_context()` before wiring this command so an absolute
`tickets_dir` derives `project_root` from the tickets directory path, not from
`Path.cwd()`:

- Resolve `raw_tickets_dir` against `Path.cwd()` only when it is relative.
- Run `discover_project_root()` starting from the resolved tickets directory
  candidate, then validate with `resolve_tickets_dir(..., project_root=project_root)`.
- Use `Path.cwd()` only as a fallback for legacy relative invocations where the
  tickets directory path cannot be resolved yet.
- Add subprocess tests that run `ticket_doctor.py activate-runtime
  /absolute/project/docs/tickets` from both the project root and a non-project
  cwd; both must bind the same `project_root`. A relative `docs/tickets`
  invocation may continue to require project-root cwd.

Then call:

```python
from scripts.ticket_runtime_readiness import activate_runtime_readiness, proof_path_for_project

proof = activate_runtime_readiness(
    project_root=project_root,
    marketplace_path=args.marketplace_path,
    remote_marketplace_name=args.remote_marketplace_name,
)
proof_path = proof_path_for_project(project_root)
response = _response(
    "ok",
    {
        "mode": "activate-runtime",
        "proof_path": str(proof_path),
        "proof": proof,
    },
    "Ticket runtime readiness activated.",
)
```

On `RuntimeReadinessError`, return:

```python
_response(
    "policy_blocked",
    {"mode": "activate-runtime", "error_code": "runtime_readiness_failed"},
    str(exc),
)
```

Do not add `--cache-root` to activation. The installed root must come from app-server `hooks/list` identity and installed-cache skill paths, not from `plugin/read`.
Do not add `--plugin-root` to activation. The running root must come from `running_plugin_root()` / `Path(__file__).resolve().parents[1]` so source scripts cannot impersonate installed-cache execution.

- [ ] **Step 6: Keep diagnose read-only**

In `ticket_triage.py`, keep `runtime_probe_output` classification read-only. If you add proof inspection to `diagnose`, expose it under `runtime.activation_proof` with states like `not_found`, `present_valid`, `present_invalid`, or `expired`, but do not write or rewrite proof.

- [ ] **Step 7: Run tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py tests/test_doctor.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit activation candidate and doctor skeleton**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py
git commit -m "feat(ticket): build runtime readiness proof candidate"
```

Expected: commit contains candidate proof construction, atomic proof helpers,
doctor skeleton tests, and no production path that can write activated proof
without post-proof gated smokes.

---

### Task 5: Execute-Surface Propagation And Engine Gate

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Add: `plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py`
- Add: `plugins/turbo-mode/ticket/scripts/ticket_update_agent.py`
- Modify: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Add: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_capture.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ingest.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing engine gate tests**

In `tests/test_execute.py`, add:

- `request_origin=agent` `auto_audit` execute with full hook-mediated trust triple and `execute_surface="direct_execute"` fails with `error_code == "runtime_readiness_required"` when proof is absent.
- same request succeeds when a valid proof is written under `<project_root>/.codex/ticket-runtime-proof.json` and executing plugin root matches. Source-suite success must use an internal test seam to inject the installed executing root or verifier; it must not make source checkout execution look installed in production.
- a final proof with `status="activated"` and valid bootstrap raw evidence but no
  passing `post_activation_gated_smokes` for `direct_execute` still fails normal
  `engine_execute()` with `error_code == "runtime_readiness_required"`.
- a proof whose `gated_execute_surfaces` names `capture_execute` or
  `update_execute` but whose `post_activation_gated_smokes.surface_results` lacks
  the current `execute_surface` fails normal `engine_execute()` for that surface.
- user execute remains governed by existing trust triple and does not require runtime readiness proof.
- agent execute with missing hook-mediated provenance still fails with existing trust error before readiness.
- agent execute with `hook_request_origin="user"` is accepted as current hook membrane provenance and remains governed by `request_origin="agent"` policy.
- ordinary `ticket_engine_agent.py execute` cannot bypass readiness by setting
  `execute_surface="activation_smoke"` or any payload field.
- ordinary `ticket_engine_agent.py execute` cannot use a path-shaped candidate
  smoke root plus `runtime_readiness_proof_project_root` to mutate the proof
  target's real `docs/tickets`; candidate mode must reject any payload whose
  command, payload path, tickets dir, or proof root differs from the exact
  contained post-smoke tuple.
- the dedicated activation-smoke entrypoint can pass
  `runtime_readiness_required=False` only for `execute_surface="activation_smoke"`
  and only after smoke containment validation succeeds.
- `runtime_readiness_required=False` is not exposed through stage-model payloads,
  CLI flags, capture wrappers, or update wrappers.
- external execute payload with `execute_surface="ingest"` is rejected at the stage-model boundary with `parse_error`.
- external execute payload with `execute_surface="activation_smoke"` is rejected
  at the stage-model boundary with `parse_error`.
- `_dispatch_ingest()` reaches `engine_execute()` with `runtime_readiness_required=False` through an internal argument, not through payload-controlled `execute_surface`.

Expected failing assertion pattern:

```python
resp = engine_execute(
    action="create",
    ticket_id=None,
    fields={"title": "Agent create", "problem": "Needs runtime proof", "priority": "medium"},
    session_id="agent-session",
    request_origin="agent",
    dedup_override=False,
    dependency_override=False,
    tickets_dir=tmp_tickets,
    autonomy_config=AutonomyConfig(mode="auto_audit", max_creates=5),
    hook_injected=True,
    hook_request_origin="user",
    classify_intent="create",
    classify_confidence=0.95,
    dedup_fingerprint=dedup_fingerprint("Needs runtime proof", []),
    execute_surface="direct_execute",
)

assert resp.state == "policy_blocked"
assert resp.error_code == "runtime_readiness_required"
```

- [ ] **Step 2: Add failing surface propagation tests**

In `tests/test_capture.py`, assert successful user `capture execute` calls dispatch with `execute_surface == "capture_execute"`, `request_origin == "user"`, and `runtime_readiness_payload_path == payload_path` by monkeypatching `dispatch_stage`. Add separate tests for the hardcoded agent capture wrapper path that `prepare` and `execute` both run with `request_origin == "agent"` without reading that origin from payload or hook metadata, and that execute preserves the prepared payload's saved execute fingerprint when the hook-injected trust fields are unchanged.

In `tests/test_update_refinement.py`, assert successful user `update execute` calls dispatch with `execute_surface == "update_execute"`, `request_origin == "user"`, and `runtime_readiness_payload_path == payload_path`. Add separate tests for the hardcoded agent update wrapper path that `prepare` and `execute` both run with `request_origin == "agent"` without reading that origin from payload or hook metadata, and that execute preserves the prepared payload's saved execute fingerprint when the hook-injected trust fields are unchanged.

In `tests/test_engine_runner.py`, assert `RunnerContext.payload_path` is the resolved script-read path, `RunnerContext.runtime_readiness_command` is normalized by `ticket_command_identity()`, and exact post-smoke payloads derive `RunnerContext.runtime_readiness_proof_project_root` from the payload path. Assert `run(... execute ...)` passes these internal readiness channels into `dispatch_stage()` only for execute.

In `tests/test_ingest.py`, assert `_dispatch_ingest()` calls `engine_execute()` with `runtime_readiness_required=False`, no `runtime_readiness_payload_path`, and never accepts `execute_surface` from the ingest envelope payload.

In `tests/test_hook.py`, add hook membrane tests that:

- allow canonical `python3 -B <PLUGIN_ROOT>/scripts/ticket_capture_agent.py prepare <PAYLOAD>` and `python3 -B <PLUGIN_ROOT>/scripts/ticket_capture_agent.py execute <PAYLOAD>`, injecting the same trust fields as `ticket_capture.py` for both subcommands.
- allow canonical `python3 -B <PLUGIN_ROOT>/scripts/ticket_update_agent.py prepare <PAYLOAD>` and `python3 -B <PLUGIN_ROOT>/scripts/ticket_update_agent.py execute <PAYLOAD>`, injecting the same trust fields as `ticket_update.py` for both subcommands.
- deny noncanonical agent wrapper command shapes such as `python3 -BB ...`.
- keep unknown `ticket_*.py` scripts denied by Branch 3.

- [ ] **Step 3: Run tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_hook.py \
  -q
```

Expected: FAIL because execute surfaces and gate are missing.

- [ ] **Step 4: Add `execute_surface` to stage models and runner**

In `ExecuteInput`, add:

```python
execute_surface: str
```

In `ticket_stage_models.py`, add:

```python
_EXTERNAL_EXECUTE_SURFACES = frozenset({"direct_execute", "capture_execute", "update_execute"})


def _get_execute_surface(payload: dict[str, Any]) -> str:
    value = _get_str(payload, "execute_surface", default="direct_execute")
    if value not in _EXTERNAL_EXECUTE_SURFACES:
        raise PayloadError(
            f"execute_surface must be one of {sorted(_EXTERNAL_EXECUTE_SURFACES)}; got {value!r}",
            code="parse_error",
            state="escalate",
        )
    return value
```

In `ExecuteInput.from_payload()`, derive:

```python
execute_surface=_get_execute_surface(payload)
```

In `ticket_engine_runner.py`, carry the script-read payload path as internal
runner context. It is needed only so the candidate proof verifier can bind a
post-proof smoke to the exact payload file that the installed script executed:

```python
@dataclass(frozen=True)
class RunnerContext:
    payload: dict[str, Any]
    payload_path: Path
    runtime_readiness_command: str
    runtime_readiness_proof_project_root: Path | None
    tickets_dir: Path
    request_origin: str
```

`load_runner_context()` must set `payload_path=payload_path.resolve()` and
`runtime_readiness_command` to the canonical installed Bash command shape
(`python3 [-B] <installed-script> <subcommand> <absolute-payload-path>`) when
it returns `RunnerContext`. The proof verifier must compare normalized command
identity with `ticket_command_identity()`, not raw command strings. For
activation post-smoke payload paths under
`<PROOF_TARGET_PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/<post-smoke-directory>/`,
it must also set `runtime_readiness_proof_project_root` to the real proof target
root derived from the payload path. Do not copy these values into the stage
payload.

Thread that context through `run()`, `dispatch_stage()`, and `_dispatch()`:

```python
def dispatch_stage(
    subcommand: str,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
    *,
    runtime_readiness_payload_path: Path | None = None,
    runtime_readiness_command: str | None = None,
    runtime_readiness_proof_project_root: Path | None = None,
) -> EngineResponse:
    return _dispatch(
        subcommand,
        payload,
        tickets_dir,
        request_origin,
        runtime_readiness_payload_path=runtime_readiness_payload_path,
        runtime_readiness_command=runtime_readiness_command,
        runtime_readiness_proof_project_root=runtime_readiness_proof_project_root,
    )
```

`run()` must pass `runtime_readiness_payload_path=context.payload_path` and
`runtime_readiness_command=context.runtime_readiness_command` only when
`subcommand == "execute"`. It must pass
`runtime_readiness_proof_project_root=context.runtime_readiness_proof_project_root`
only for exact activation post-smoke execute payloads. Prepare, classify, plan,
preflight, and ingest do not pass this internal candidate-proof channel.

In `ticket_engine_runner._dispatch()`, accept the same keyword-only
`runtime_readiness_payload_path` and `runtime_readiness_command` parameters and
pass `execute_surface=inp.execute_surface`, `runtime_readiness_required=True`, and
`runtime_readiness_payload_path=runtime_readiness_payload_path` plus
`runtime_readiness_command=runtime_readiness_command` plus
`runtime_readiness_proof_project_root=runtime_readiness_proof_project_root` to
`engine_execute()`.

In `_dispatch_ingest()`, pass `execute_surface="direct_execute"` and `runtime_readiness_required=False` to its internal `engine_execute()` call. Do not use `"ingest"` as an `execute_surface` value anywhere.

Also update `load_runner_context()` so `hook_request_origin` is no longer
required to match the hardcoded entrypoint `request_origin`. Keep rejecting
missing trust provenance for `execute`/`ingest`, but treat the hook origin as
observed runtime metadata. Current Codex injects `"user"` even when the
entrypoint is `ticket_engine_agent.py`; the entrypoint remains the policy
selector for `request_origin`.

- [ ] **Step 5: Set wrapper execute surfaces and agent wrapper selectors**

Refactor `ticket_capture.py` so its internal run function accepts a hardcoded
`request_origin` argument from the entrypoint, defaulting to `"user"` for the
existing script. Do not add a caller-supplied CLI flag or payload field for
agent selection. Prepare and execute must both load wrapper context with the
entrypoint-selected `request_origin` so the script identity, not hook metadata
or payload content, selects the policy origin. Execute still passes the payload
path and current command through the internal `runtime_readiness_payload_path`
and `runtime_readiness_command` channels after the wrapper prepare/fingerprint
checks pass. The wrapper context must expose the same canonical command string
as the shared runner context.

In `ticket_capture.py`, after all prepare/fingerprint checks pass and immediately before dispatching execute:

```python
execute_payload = dict(payload)
execute_payload.pop("execute_surface", None)
execute_payload["execute_surface"] = "capture_execute"
response = _engine_response_to_dict(
    dispatch_stage(
        "execute",
        execute_payload,
        tickets_dir,
        request_origin,
        runtime_readiness_payload_path=payload_path,
        runtime_readiness_command=runtime_readiness_command,
        runtime_readiness_proof_project_root=runtime_readiness_proof_project_root,
    )
)
```

Add `ticket_capture_agent.py` as a tiny entrypoint that imports the refactored
capture runner and calls it with `request_origin="agent"`. This file is the
only supported agent policy selector for capture wrapper `prepare` and
`execute`.

Refactor `ticket_update.py` the same way: the existing script defaults to
`request_origin="user"`, no CLI or payload value can select agent mode, prepare
and execute both use the entrypoint-selected `request_origin`, and execute
passes the payload path and current command through `runtime_readiness_payload_path`
and `runtime_readiness_command` only after the wrapper prepare/fingerprint
checks pass. The wrapper context must expose the same canonical command string
as the shared runner context.

In `ticket_update.py`, after all prepare/fingerprint checks pass and immediately before dispatching execute:

```python
execute_payload = dict(payload)
execute_payload.pop("execute_surface", None)
execute_payload["execute_surface"] = "update_execute"
response = _engine_response_to_dict(
    dispatch_stage(
        "execute",
        execute_payload,
        tickets_dir,
        request_origin,
        runtime_readiness_payload_path=payload_path,
        runtime_readiness_command=runtime_readiness_command,
        runtime_readiness_proof_project_root=runtime_readiness_proof_project_root,
    )
)
```

Add `ticket_update_agent.py` as a tiny entrypoint that imports the refactored
update runner and calls it with `request_origin="agent"`. This file is the only
supported agent policy selector for update wrapper `prepare` and `execute`.

This makes wrapper surfaces internal to the wrapper execute step. A stale or malicious `execute_surface` already present in the payload cannot change the saved preview fingerprint or select a bypass, and a caller cannot obtain `request_origin="agent"` for wrapper prepare or execute without using the hardcoded agent wrapper entrypoint.

- [ ] **Step 6: Update hook wrapper allowlist**

In `hooks/ticket_engine_guard.py`, update the canonical wrapper parsers so they
accept exactly these scripts:

- capture wrapper scripts: `ticket_capture.py`, `ticket_capture_agent.py`.
- update wrapper scripts: `ticket_update.py`, `ticket_update_agent.py`.

Keep the same command shape restrictions that exist today: `python3`, optional
single `-B`, exact installed plugin-root script path, subcommand, payload path
without whitespace, and no broad `ticket_*.py` wildcard. Unknown Ticket scripts
must still be denied by Branch 3. The agent wrapper allowlist must cover both
`prepare` and `execute`; otherwise capture/update post-proof setup cannot
produce a prepared payload whose saved execute fingerprint survives the later
hook-mediated execute command.

- [ ] **Step 7: Add the engine gate**

In `ticket_engine_core.py`, use the `execute_surface` and
`runtime_readiness_required` parameters introduced for the activation-smoke
entrypoint in Task 3. If they were not added there, add them now:

```python
execute_surface: str = "direct_execute",
runtime_readiness_required: bool = True,
runtime_readiness_verifier: Any | None = None,
runtime_readiness_executing_plugin_root: Path | None = None,
runtime_readiness_payload_path: Path | None = None,
runtime_readiness_command: str | None = None,
runtime_readiness_proof_project_root: Path | None = None,
```

Verify the transport-layer trust check was already changed in Task 3 so
`hook_request_origin != request_origin` is metadata-only and does not block the
activation smoke. Do not reintroduce equality between hook-observed origin and
entrypoint-selected `request_origin`. If Task 3 did not make this change, stop
and patch that ordering defect before wiring the readiness gate.

After the updated transport-layer trust triple and structural execute
prerequisites, and before audit writes, add:

```python
if request_origin == "agent" and config.mode == "auto_audit" and runtime_readiness_required:
    readiness_error = _runtime_readiness_error(
        tickets_dir=tickets_dir,
        execute_surface=execute_surface,
        runtime_readiness_verifier=runtime_readiness_verifier,
        runtime_readiness_executing_plugin_root=runtime_readiness_executing_plugin_root,
        runtime_readiness_payload_path=runtime_readiness_payload_path,
        runtime_readiness_command=runtime_readiness_command,
        runtime_readiness_proof_project_root=runtime_readiness_proof_project_root,
    )
    if readiness_error is not None:
        return readiness_error
```

Add helper:

```python
def _runtime_readiness_error(
    *,
    tickets_dir: Path,
    execute_surface: str,
    runtime_readiness_verifier: Any | None = None,
    runtime_readiness_executing_plugin_root: Path | None = None,
    runtime_readiness_payload_path: Path | None = None,
    runtime_readiness_command: str | None = None,
    runtime_readiness_proof_project_root: Path | None = None,
) -> EngineResponse | None:
    if execute_surface not in {"direct_execute", "capture_execute", "update_execute"}:
        return EngineResponse(
            state="policy_blocked",
            message=f"Unknown execute surface for runtime readiness. Got: {execute_surface!r:.100}",
            error_code="runtime_readiness_required",
        )
    from scripts.ticket_paths import discover_project_root
    from scripts.ticket_runtime_readiness import (
        RuntimeReadinessError,
        load_activation_candidate_proof,
        load_activation_proof,
        post_smoke_candidate_context_for_payload,
        verify_activation_candidate_for_post_smoke,
        verify_activation_closeout_proof_for_execute,
    )

    discovered_project_root = discover_project_root(tickets_dir)
    proof_project_root = runtime_readiness_proof_project_root or discovered_project_root
    if proof_project_root is None:
        return EngineResponse(
            state="policy_blocked",
            message="Runtime readiness requires a project root with .codex or .git marker.",
            error_code="runtime_readiness_required",
        )
    post_smoke_context = post_smoke_candidate_context_for_payload(
        execute_surface=execute_surface,
        payload_path=runtime_readiness_payload_path,
    )
    if runtime_readiness_proof_project_root is not None and post_smoke_context is None:
        return EngineResponse(
            state="policy_blocked",
            message="Runtime readiness proof-root channel is only valid for exact activation post-smoke payloads.",
            error_code="runtime_readiness_required",
        )
    if post_smoke_context is not None:
        expected_proof_root, post_smoke_run_nonce = post_smoke_context
        if runtime_readiness_command is None or runtime_readiness_payload_path is None:
            return EngineResponse(
                state="policy_blocked",
                message="Runtime readiness candidate mode requires exact command and payload path.",
                error_code="runtime_readiness_required",
            )
        if proof_project_root.resolve() != expected_proof_root.resolve():
            return EngineResponse(
                state="policy_blocked",
                message="Runtime readiness candidate proof root does not match post-smoke payload root.",
                error_code="runtime_readiness_required",
            )
        try:
            candidate = load_activation_candidate_proof(proof_project_root)
            verify_activation_candidate_for_post_smoke(
                candidate,
                project_root=proof_project_root,
                executing_plugin_root=runtime_readiness_executing_plugin_root
                or Path(__file__).resolve().parents[1],
                execute_surface=execute_surface,
                run_nonce=post_smoke_run_nonce,
                command=runtime_readiness_command,
                payload_path=runtime_readiness_payload_path,
                tickets_dir=tickets_dir,
            )
            return None
        except RuntimeReadinessError as exc:
            return EngineResponse(
                state="policy_blocked",
                message=f"Runtime readiness candidate rejected contained post-smoke execute: {exc}",
                error_code="runtime_readiness_required",
            )
    try:
        proof = load_activation_proof(proof_project_root)
        verifier = runtime_readiness_verifier or verify_activation_closeout_proof_for_execute
        verifier(
            proof,
            project_root=proof_project_root,
            executing_plugin_root=runtime_readiness_executing_plugin_root
            or Path(__file__).resolve().parents[1],
            execute_surface=execute_surface,
        )
    except RuntimeReadinessError as exc:
        return EngineResponse(
            state="policy_blocked",
            message=f"Runtime readiness required before activation-gated auto_audit execute: {exc}",
            error_code="runtime_readiness_required",
        )
    return None
```

The only production caller allowed to pass `runtime_readiness_required=False`
with `execute_surface="activation_smoke"` is
`ticket_engine_activation_smoke.py`, and that entrypoint must perform the smoke
root/tickets-dir containment checks before calling `engine_execute()`. Normal
runner dispatch, `ticket_engine_agent.py`, capture wrappers, and update wrappers
must always use `runtime_readiness_required=True` for external execute payloads.

Thread the internal-only `runtime_readiness_verifier` and
`runtime_readiness_executing_plugin_root` parameters only through tests and
direct internal calls. Thread `runtime_readiness_payload_path` and
`runtime_readiness_proof_project_root` only as keyword-only internal values
through `RunnerContext`, `run()`, `dispatch_stage()`, `_dispatch()`, and the
capture/update wrapper execute calls so the candidate verifier can prove
contained post-smoke payload identity. The proof-root channel is valid only for
exact activation post-smoke payloads; if it is present for any other execute,
the gate must fail closed instead of loading a proof from that alternate root.
Stage-model payload parsing must not accept these fields, no CLI flag or
environment variable may expose them, and production code must default the
executing plugin root to `Path(__file__).resolve().parents[1]`.

If this helper causes import cycles, move it into `ticket_runtime_readiness.py` and keep `ticket_engine_core.py` with a minimal import inside the helper.

- [ ] **Step 8: Add post-proof gated surface smokes**

In `ticket_runtime_readiness.py`, implement
`run_post_activation_gated_smokes()` and
`_verify_post_activation_gated_smokes()`, plus
`_verify_post_activation_gated_smoke_for_surface()` for the normal execute gate
and `_proof_gated_execute_surfaces()` for closeout iteration. Then replace the
Task 4 placeholder `activate_runtime_readiness()` with the production writer.
Also add `refresh_aggregate_transcript_hash()` so post-proof app-server rows
that are appended during gated smokes are included in
`app_server_transcript_sha256` before closeout verification.

The runner must execute live app-server turns after the candidate proof file is
written and before final proof promotion, and must prove the exact surfaces listed in
`ACTIVATING_EXECUTE_SURFACES`:

- `direct_execute`: canonical `ticket_engine_agent.py execute <PAYLOAD>`.
- `capture_execute`: canonical `ticket_capture_agent.py prepare <PAYLOAD>`
  setup followed by canonical `ticket_capture_agent.py execute <PAYLOAD>`.
- `update_execute`: canonical `ticket_update_agent.py prepare <PAYLOAD>` setup
  followed by canonical `ticket_update_agent.py execute <PAYLOAD>`.

Payload construction is part of the proof, not an implementation detail:

- For each surface, create a separate smoke project root at
  `.codex/ticket-runtime-smoke/<run_nonce>/<post-smoke-directory>/` with its own
  `.codex/ticket.local.md`, `docs/tickets/`, `raw/`, and exact payload file:
  `post-direct/post-direct-payload.json`,
  `post-capture/post-capture-payload.json`, or
  `post-update/post-update-payload.json` according to `execute_surface`. The
  payload path passed to the installed script must equal that exact file and
  must be the same path later passed through `runtime_readiness_payload_path`.
  Because this smoke root intentionally has its own `.codex/` marker, the
  wrapper/runner must also pass `runtime_readiness_proof_project_root` for
  post-smoke execute so the gate loads
  `<PROOF_TARGET_PROJECT_ROOT>/.codex/ticket-runtime-proof.candidate.json`
  rather than a candidate under the disposable smoke project.
- `direct_execute` payload setup writes a fully planned create payload directly:
  `action="create"`, valid required fields, `tickets_dir="docs/tickets"`,
  `classify_intent="create"`, `classify_confidence=0.95`,
  recomputed `dedup_fingerprint`, `autonomy_config` matching the smoke
  `.codex/ticket.local.md`, the shared `ticket_runtime_readiness_nonce`, and no
  caller-supplied `execute_surface` override other than the explicit
  `"direct_execute"` value parsed by the stage model.
- `capture_execute` payload setup first writes a normal capture payload with
  `capture` fields sufficient for `ticket_capture_agent.py prepare`. Run
  prepare through a live app-server turn, not a local subprocess, using the same
  contained cwd, workspace roots, sandbox policy, installed hook, and hardcoded
  `ticket_capture_agent.py` entrypoint that execute will use. The exact command
  is `ticket_capture_agent.py prepare <PAYLOAD>`, and it must populate
  `fields`, `capture_prepare`, preview, classify/plan/preflight data, and all
  prepare fingerprints. That prepare turn is fixture setup and is not counted as
  the gated proof, but it is proof evidence. After prepare succeeds, copy the
  prepared payload bytes to `raw/capture-payload-after-prepare.json` and
  `raw/capture-payload-before-execute.json`. The app-server execute turn must
  run in the same app-server thread/session and execute exactly
  `ticket_capture_agent.py execute <PAYLOAD>`. Activation must verify that the
  execute-turn hook injection leaves `session_id`, `hook_injected`, and
  `hook_request_origin` identical to the prepared payload values before the
  wrapper reaches its saved `execute_fingerprint` check, then the wrapper injects
  `execute_surface="capture_execute"` before `dispatch_stage()`.
- `update_execute` payload setup must seed exactly one mutable ticket under the
  contained post-update `docs/tickets/` before prepare. Compute the live
  `target_fingerprint` from that seeded ticket, write an update payload with
  `ticket_id`, `update` fields, the shared nonce, and the contained
  `tickets_dir`, then run `ticket_update_agent.py prepare <PAYLOAD>` through a
  live app-server turn using the same contained cwd, workspace roots, sandbox
  policy, installed hook, and hardcoded agent wrapper entrypoint that execute
  will use. Prepare must populate `fields`, `update_prepare`, preview,
  classify/plan/preflight data, and all prepare fingerprints. After prepare
  succeeds, copy the prepared payload bytes to
  `raw/update-payload-after-prepare.json` and
  `raw/update-payload-before-execute.json`. The app-server execute turn must run
  in the same app-server thread/session and execute exactly
  `ticket_update_agent.py execute <PAYLOAD>`. Activation must verify that the
  execute-turn hook injection leaves `session_id`, `hook_injected`, and
  `hook_request_origin` identical to the prepared payload values before the
  wrapper reaches its saved `execute_fingerprint` check, then the wrapper
  injects `execute_surface="update_execute"` before `dispatch_stage()`.
- If capture or update prepare returns `stale_plan`, `need_fields`, `not_found`,
  policy failure, or any state other than `ready_to_execute`, activation fails
  before final proof promotion. Do not patch around wrapper prepare gates or
  weaken the wrapper fingerprint checks to make post-proof smokes pass.
- If capture or update execute returns `stale_plan` before reaching the runtime
  readiness gate, activation fails with a wrapper trust-fingerprint mismatch
  diagnostic that records the prepared trust inputs and execute-time trust
  inputs. Do not treat that as proof of readiness failure.

Each post-proof smoke must:

- use the same pinned app-server policy as the bootstrap smoke:
  `approvalPolicy="never"`, contained absolute `cwd`,
  `runtimeWorkspaceRoots=[str(post_smoke_project_root)]`, workspace-write
  `sandboxPolicy` with only that root writable, and fail-fast handling for any
  command/file/permissions approval request.
- run with `runtime_readiness_required=True` through the normal installed script,
  not `ticket_engine_activation_smoke.py`.
- use `.codex/ticket-runtime-proof.candidate.json` with
  `status="activation_in_progress"` through
  `verify_activation_candidate_for_post_smoke()`. This candidate verifier mode
  runs before any final proof lookup, receives the current command string and
  proof target project root, and must reject anything other than the exact
  command/payload/tickets-dir/proof-root tuple for the candidate nonce. The
  final `.codex/ticket-runtime-proof.json` must not exist as an activated proof
  until these smokes pass.
- use a distinct contained smoke tickets dir under
  `.codex/ticket-runtime-smoke/<run_nonce>/<post-smoke-directory>/docs/tickets`.
- create no target-project `docs/tickets` files and no target-project
  `.codex/ticket.local.md`.
- record schema-shaped raw `commandExecution`, same-turn installed
  `hook/completed`, parsed engine stdout, ticket file hash, audit hash, and
  per-surface payload snapshots in `raw/post-activation-gated-events.jsonl` and
  per-surface raw files. For direct execute, record payload before/after hashes.
  For capture/update, record payload before prepare, payload after prepare,
  payload before execute, wrapper stdout cleanup status, and payload after
  execute only if the wrapper does not delete the consumed payload.
- for capture/update, record and verify a
  `wrapper_trust_fingerprint_inputs` object containing the prepared
  `session_id`, `hook_injected`, `hook_request_origin`, contained `tickets_dir`,
  payload path, saved `execute_fingerprint`, execute-time trust fields, and a
  boolean `stable_between_prepare_and_execute` that must be true.
- fail activation if the app-server turn or turns have zero, duplicate, extra, or wrong
  commands; missing hook completion; unsupported hook-output warnings; non-
  expected engine state (`ok_create` for `direct_execute` and `capture_execute`,
  `ok_update` for `update_execute`); stale proof rejection; stale wrapper
  prepare/fingerprint state, including changed wrapper trust fingerprint inputs
  between prepare and execute; or mutation outside the contained post-smoke
  tickets dir.

If any post-proof gated smoke fails, `activate_runtime_readiness()` must write a
final `.codex/ticket-runtime-proof.json` failure marker with
`status="activation_failed"` and return a `RuntimeReadinessError`. It must not
leave a final proof that normal `engine_execute()` accepts as activated. The
temporary `.codex/ticket-runtime-proof.candidate.json` may remain for
diagnostics, but normal gated execute must reject that candidate path/status.
This is an intentional fail-closed operator tradeoff: a failed reactivation
replaces any previous activated proof for the same project root. If preserving a
previous valid proof is required, implement a separate failure artifact before
this step rather than silently keeping stale activation state.

Production writer shape:

```python
def activate_runtime_readiness(
    *,
    project_root: Path,
    marketplace_path: Path,
    remote_marketplace_name: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect live evidence, prove actual gated paths, and write activation proof."""
    active_now = now or datetime.now(UTC)
    executing_plugin_root = running_plugin_root()
    candidate = _build_activation_proof_candidate(
        project_root=project_root,
        marketplace_path=marketplace_path,
        remote_marketplace_name=remote_marketplace_name,
        now=active_now,
        inventory_collector=collect_app_server_inventory,
        smoke_runner=run_hook_membrane_smoke,
        agentcontrol_smoke_runner=run_agentcontrol_hook_traversal_smoke,
    )
    candidate["status"] = ACTIVATION_IN_PROGRESS_STATUS
    write_activation_candidate_atomic(project_root, candidate)
    try:
        candidate["post_activation_gated_smokes"] = run_post_activation_gated_smokes(
            project_root=project_root,
            candidate_proof=candidate,
            installed_cache_root=Path(candidate["ticket_plugin"]["installed_cache_root"]),
            run_nonce=str(candidate["run_nonce"]),
        )
        refresh_aggregate_transcript_hash(candidate, project_root=project_root)
        proof = dict(candidate)
        proof["status"] = ACTIVATED_STATUS
        verify_activation_closeout_proof(
            proof,
            project_root=project_root.resolve(),
            executing_plugin_root=executing_plugin_root.resolve(),
            now=active_now,
        )
        write_activation_proof_atomic(project_root, proof)
    except RuntimeReadinessError:
        write_activation_failure_marker_atomic(project_root, candidate)
        raise
    return proof
```

Add tests proving:

- bootstrap-only candidate proof is enough for the contained post-proof smoke
  verifier to exercise the normal installed scripts, but normal gated execute
  rejects the candidate status/path for target-project `docs/tickets`.
- candidate post-smoke verification ignores an existing activated final proof
  and accepts only the exact candidate nonce, surface, command, payload path,
  and contained tickets dir.
- candidate post-smoke verification loads the candidate from the proof target
  project root even when the smoke `tickets_dir` is under a disposable smoke
  project that has its own `.codex/` marker.
- passing `runtime_readiness_proof_project_root` for a non-post-smoke execute
  fails closed instead of authorizing a normal mutation from an alternate root.
- activation closeout requires all surfaces listed in `gated_execute_surfaces`.
- a failed `capture_execute` or `update_execute` post-smoke invalidates the
  proof instead of silently narrowing scope.
- if the implementation deliberately supports only direct execute, the proof
  builder must narrow `gated_execute_surfaces` to `["direct_execute"]` before
  writing proof; keeping capture/update while skipping their smokes fails.

- [ ] **Step 9: Run focused gate tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_hook.py \
  -q
```

Expected: PASS.

- [ ] **Step 10: Commit engine gate**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_stage_models.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_update_agent.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): gate agent execute on runtime readiness"
```

Expected: commit contains only execute-surface and gate changes.

---

### Task 6: Docs And Skill Contract

**Files:**
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ux.py`

- [ ] **Step 1: Read writing-principles before skill/reference edits**

```bash
sed -n '1,220p' .codex/skills/writing-principles/SKILL.md
```

Expected: writing guidance is read before editing `SKILL.md` or instruction-style docs. If the repo-local file is absent, read `/Users/jp/.agents/skills/writing-principles/SKILL.md`.

- [ ] **Step 2: Add failing docs contract tests**

In `tests/test_docs_contract.py`, add assertions that:

- `ticket-contract.md` says activation readiness requires live app-server inventory and live Codex-mediated hook smoke.
- `ticket-contract.md` says activation readiness proves installed hook-mediated mutation wiring, not caller identity, and does not require `agent_id`.
- `ticket-contract.md` rewrites the existing Autonomy Model paragraphs so
  `agent_id` is not authoritative on current Codex, `hook_request_origin` is
  observed metadata, and entrypoint-selected `request_origin` remains the policy
  selector. Do not leave the old `agent_id` / matching-origin model next to the
  new activation section.
- `ticket-contract.md` updates the public error-code table and UX/recovery
  wording to include `runtime_readiness_required` for gated engine execute
  failures, or else the implementation must use an already documented
  `policy_blocked` code with a structured readiness reason. The plan currently
  uses `runtime_readiness_required`, so the default patch is to add it.
- `ticket-contract.md` says the activation smoke must create a contained disposable smoke project with `.codex/ticket.local.md` set to `auto_audit`, include a matching `autonomy_config` snapshot in the payload, and prove hook membrane traversal (`ticket_engine_activation_smoke.py`, schema-shaped `commandExecution`, installed Ticket `hook/completed`, `hook_injected=true`, `hook_request_origin=user` on current Codex, host `session_id`, command/payload/nonce binding) before `auto_audit` can be gated as ready.
- `ticket-contract.md` says the activation bootstrap bypass is only for the
  dedicated activation-smoke entrypoint and contained smoke tickets directory;
  ordinary agent execute, capture execute, update execute, and payload fields
  cannot select it.
- `ticket-contract.md` says AgentControl child smoke is traversal corroboration only, not caller-identity proof.
- `ticket-contract.md` says `plugin/read` source metadata is not installed-root proof; installed root comes from `hooks/list` and is corroborated by prefixed `ticket:*` skills with installed-cache paths.
- `ticket-contract.md` says `.codex/ticket-runtime-proof.json` cannot be written from source checkout diagnostics, fixtures, handwritten JSON, or direct hook-script smoke.
- `ticket-contract.md` says the engine gate recomputes plugin, hook, guard,
  installed code, Codex, raw evidence hashes, raw evidence semantics, command,
  payload hashes, parsed `raw/engine-stdout.json`, smoke ticket file, smoke
  audit JSONL, nonce, current-surface post-proof smoke evidence, and age identity
  at gate time instead of trusting JSON shape alone.
- `ticket-contract.md` says app-server smoke turns pin `approvalPolicy="never"`,
  contained `cwd`, runtime workspace roots, and workspace-write sandbox policy,
  and fail closed on any command/file/permissions approval request.
- `ticket-contract.md` says external execute payloads cannot set `execute_surface="ingest"`.
- `ticket-contract.md` lists gated surfaces `direct_execute`, `capture_execute`, `update_execute`, and excluded mutation paths `ingest_dispatch` and `activation_smoke_bootstrap`; it must not describe `ingest` as a public execute surface.
- `ticket-contract.md` says activation closeout and normal execute gating must
  require post-proof live smokes through the actual gated installed surfaces, not
  only the bootstrap entrypoint.
- `ticket-contract.md` says `.codex/ticket-runtime-proof.candidate.json` with
  `status=activation_in_progress` is non-authorizing for normal execute and may
  be used only for contained post-smoke validation.
- `ticket-contract.md` says capture/update post-proof smokes must use prepared
  wrapper payloads with valid `capture_prepare` / `update_prepare` fingerprints
  and an update target seeded under the contained smoke project. Prepare and
  execute must both be app-server/hook mediated through the same hardcoded agent
  wrapper path, and the docs must require stable wrapper trust-fingerprint inputs
  across that boundary.
- `ticket-contract.md` says wrapper `request_origin=agent` can only come from hardcoded agent wrapper entrypoints, not hook metadata, CLI flags, or payload fields.
- `ticket-doctor/SKILL.md` documents `activate-runtime` separately from `diagnose`.
- `ticket-doctor/SKILL.md` says activation may leave an activated `.codex/ticket-runtime-proof.json` only after live inventory, live bootstrap smokes, and post-proof gated surface smokes pass.
- `ticket-doctor/SKILL.md` says ordinary `diagnose` remains source/cache/storage evidence and not live activation proof, and does not claim broad source-vs-cache equality unless a source manifest digest comparison is implemented.

- [ ] **Step 3: Run docs contract tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_ux.py -q
```

Expected: FAIL until docs and UX/recovery mapping are updated.

- [ ] **Step 4: Patch `ticket-contract.md`**

First revise the existing `## 5. Autonomy Model` section in place:

- Replace `agent_id` as authoritative trust source with the current 0.132.0
  model: installed hook traversal plus injected `session_id`,
  `hook_injected=true`, and observed `hook_request_origin`.
- State that `hook_request_origin` is provenance metadata on current Codex and
  must not be required to match the entrypoint-selected `request_origin`.
- Preserve entrypoint-selected `request_origin` as the policy selector for user
  versus agent behavior.
- Replace the old execute-provenance paragraph so it requires hook injection,
  present hook origin metadata, and non-empty session id, but not matching hook
  origin.
- Update the error-code count/table to include `runtime_readiness_required`
  because this plan returns that code from the engine gate. If implementation
  instead chooses `policy_blocked`, update every plan snippet that currently
  asserts `runtime_readiness_required`.

Then add a section named `## Activation-Capable Runtime Readiness` containing these exact points:

- Activation proof path: `<PROJECT_ROOT>/.codex/ticket-runtime-proof.json`.
- Activation candidate path:
  `<PROJECT_ROOT>/.codex/ticket-runtime-proof.candidate.json`, with
  `status=activation_in_progress`, is non-authorizing for normal execute.
- Proof target root: `<PROJECT_ROOT>` is the real repository being activated.
  Disposable smoke roots under `.codex/ticket-runtime-smoke/<run_nonce>/` may
  contain their own `.codex/` marker, but proof lookup remains bound to the
  proof target root.
- Activation proof class: installed runtime.
- Required evidence: live app-server inventory, live Codex-mediated hook membrane smoke, AgentControl child hook traversal smoke, and post-proof gated smokes for every listed gated execute surface.
- Rejected evidence: source checkout diagnostics, fixture transcripts, direct hook-script subprocesses, cache file presence, marketplace JSON, and handwritten proof JSON.
- Bound identities: project root, Ticket plugin id/version, plugin/read source metadata and digest, installed cache root derived from `hooks/list`, installed-cache `ticket:*` skill paths, plugin manifest path/hash, `hook_manifest_path`, `hook_manifest_sha256`, `guard_command`, `guard_script_path`, `guard_script_sha256`, Codex executable identity, marketplace path, cwd, pinned app-server approval/sandbox policy, app-server inventory hash, raw evidence hashes and semantics, exact smoke command/cwd from `commandExecution`, same-turn installed `hook/completed`, smoke disposable-project `auto_audit` config, smoke payload hashes or wrapper payload snapshots/deletion status, capture/update trust-fingerprint stability, parsed `raw/engine-stdout.json`, raw engine `ticket_path`, contained smoke ticket file/hash, contained smoke audit JSONL/hash, nonce, smoke session id, AgentControl child thread/turn ids, current-surface post-proof smoke evidence, and proof age.
- Bound installed code: every installed Ticket `scripts/*.py` file discovered in
  the installed cache, including helper modules such as `ticket_paths.py`,
  `ticket_trust.py`, `ticket_payloads.py`, `ticket_read.py`, `ticket_parse.py`,
  `ticket_render.py`, `ticket_validate.py`, `ticket_dedup.py`, and all mutation
  entrypoints.
- Gate behavior: the engine reloads proof JSON as untrusted input and recomputes the identities above, including closeout-level post-proof smoke evidence for the current `execute_surface`, before accepting it.
- Gated surfaces: `request_origin=agent` `auto_audit` `direct_execute`, `capture_execute`, and `update_execute`. Wrapper agent origins are selected only by dedicated hardcoded agent wrapper entrypoints, not hook metadata or caller payload.
- Excluded path: `ingest` reaches execute only through the internal ingest dispatcher; external execute payloads cannot select `execute_surface="ingest"`.
- Activation bootstrap: first activation uses the dedicated
  `ticket_engine_activation_smoke.py` entrypoint and internal
  `execute_surface="activation_smoke"` only for the contained smoke tickets dir.
  External payloads cannot select `activation_smoke`.
- Post-proof gated smokes: after the bootstrap candidate proof is written,
  activation closeout runs installed `ticket_engine_agent.py`,
  `ticket_capture_agent.py`, and `ticket_update_agent.py` through app-server
  with the normal readiness gate enabled. These smokes may use the candidate
  only for exact contained post-smoke payloads and tickets dirs. Missing or
  failed post-proof smoke invalidates activation. Capture/update smokes use
  prepared wrapper payloads with valid prepare fingerprints; their prepare and
  execute commands both run through the same app-server/hook-mediated agent
  wrapper path, and activation records stable `session_id`, `hook_injected`, and
  `hook_request_origin` evidence across the saved execute fingerprint boundary.
  Update smokes seed their target ticket under the contained smoke project.

- [ ] **Step 5: Patch UX/recovery mapping**

In `ticket_ux.py`, add `runtime_readiness_required` to the user-facing error
title and recovery-category mapping. The recovery guidance must tell the
operator to run explicit Ticket runtime activation or inspect the activation
diagnostic, not to retry a normal execute blindly. Add `tests/test_ux.py`
coverage proving responses with `error_code="runtime_readiness_required"` do
not collapse to generic `policy_blocked`.

- [ ] **Step 6: Patch `ticket-doctor/SKILL.md`**

Add `Runtime Activation` after diagnostics:

````markdown
## Runtime Activation

Use only when the user explicitly asks to activate, prove, or certify Ticket
runtime readiness. This command may write
`<PROJECT_ROOT>/.codex/ticket-runtime-proof.json` only after it collects live
app-server inventory, runs a live Codex-mediated hook smoke, and proves each
listed gated execute surface through a post-proof app-server smoke.
The smoke uses a contained disposable project under
`<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/` with its own
`auto_audit` config; it must not require or edit the target project's
`.codex/ticket.local.md`.
Every app-server smoke turn must pin approval policy and sandbox behavior so
activation fails rather than waits if the runtime requests command, file, or
permissions approval.
First activation uses the dedicated `ticket_engine_activation_smoke.py`
bootstrap entrypoint. Ordinary `ticket_engine_agent.py`, capture, update, and
payload fields cannot select the bootstrap bypass.
After the bootstrap candidate proof is present, the activation command must run
post-proof live smokes through the actual gated installed surfaces with the
normal readiness gate enabled. The bootstrap candidate lives at
`<PROJECT_ROOT>/.codex/ticket-runtime-proof.candidate.json` with
`status=activation_in_progress`; ordinary agent execute must reject that
candidate, and only exact contained post-smoke payloads may use it. If any
listed gated surface fails or is skipped, activation must write a rejected final
failure marker and report the failure.
Capture/update post-proof smokes prepare their wrapper payloads through the same
app-server/hook-mediated agent wrapper path used for execute. Activation must
fail if the prepared payload's execute-fingerprint trust inputs differ at
execute time or if the wrapper returns `stale_plan` before reaching the runtime
readiness gate.

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path <MARKETPLACE_JSON>
```

Report the result as installed-runtime activation proof. If activation fails,
report the failure reason and do not suggest editing the proof file by hand.
Do not treat `diagnose`, source/cache equality, runtime probe fixture output,
direct hook-script subprocess output, synthetic hook rows, or uncorrelated
app-server output as activation proof. On current Codex,
`hook_request_origin=user` is expected hook membrane metadata and is not a
rejection reason by itself. The proof must bind command identity from
`commandExecution` items and installed hook traversal from same-turn
`hook/completed` notifications, plus hashes for every installed Ticket
`scripts/*.py` file and separate hook/manifests. It must also bind parsed
`raw/engine-stdout.json`, the contained smoke ticket file, and the contained
smoke audit JSONL artifact; normalized proof fields alone are not mutation
success evidence.
````

- [ ] **Step 7: Run docs contract tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_ux.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit docs**

```bash
git add \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git commit -m "docs(ticket): document runtime readiness activation"
```

Expected: commit contains only docs, the Ticket UX mapping, docs tests, and UX
tests.

---

### Task 7: Final Verification And Live Activation Check

**Files:**
- Review: all changed files from Tasks 1-6.
- Optional local artifact: `<PROJECT_ROOT>/.codex/ticket-runtime-proof.json`
- Optional local artifact: `<PROJECT_ROOT>/.codex/ticket-runtime-proof.candidate.json`
- Optional local artifact: `<PROJECT_ROOT>/.codex/ticket-runtime-smoke/<run_nonce>/`

- [ ] **Step 1: Review status and diff stat**

```bash
git status --short --untracked-files=all -- \
  docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md \
  plugins/turbo-mode/ticket \
  .codex/ticket-runtime-proof.json \
  .codex/ticket-runtime-proof.candidate.json \
  .codex/ticket-runtime-smoke
git status --short --ignored --untracked-files=all -- \
  .codex/ticket-runtime-proof.json \
  .codex/ticket-runtime-proof.candidate.json \
  .codex/ticket-runtime-smoke
git diff --stat
```

Expected: only planned Ticket source, tests, docs, and this plan are changed.
Untracked new source/test files must be part of the planned implementation and
must be staged by the appropriate commit step. Local activation artifacts under
`.codex/ticket-runtime-proof.json`, `.codex/ticket-runtime-proof.candidate.json`,
or `.codex/ticket-runtime-smoke/` are allowed only after the optional live
activation step; report them explicitly and do not stage them. The proof remains
valid only while the indexed raw evidence under
`.codex/ticket-runtime-smoke/<run_nonce>/raw/` is present. Cleanup, `git clean`,
or manual deletion of raw evidence invalidates activation until the live
activation command is rerun.

- [ ] **Step 2: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_doctor.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_hook.py \
  tests/test_docs_contract.py \
  tests/test_ux.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run full Ticket suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: PASS.

- [ ] **Step 4: Run changed-path lint**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_stage_models.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_update_agent.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
```

Expected: PASS.

- [ ] **Step 5: Run whitespace gate**

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 6: Optional live installed-runtime activation**

Run this only if the user explicitly asks for live installed-runtime activation or certification, and only after the implemented source changes have been refreshed into `/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_doctor.py \
  activate-runtime /Users/jp/Projects/active/codex-tool-dev/docs/tickets \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

The command uses an absolute tickets dir so `activate-runtime` must discover the
project root from that path and remain correct even if the operator's cwd is the
installed cache or another directory.

Expected on success after installed refresh: `.codex/ticket-runtime-proof.json`
exists, verifies as installed-runtime activation closeout proof, and includes
passing `post_activation_gated_smokes` for every surface listed in
`gated_execute_surfaces`; normal `engine_execute()` also accepts each listed
surface only after verifying that surface's closeout proof. A proof that exists
but has `status="activation_failed"`, lacks post-proof gated smokes, prompts for
approval, or proves only the bootstrap entrypoint is not an activation success.
If the proof JSON exists but its indexed raw transcripts, payload snapshots,
engine output, smoke ticket, or audit artifacts have been cleaned, report
`activation evidence missing` and rerun activation instead of trusting the JSON.
If this fails because installed cache is stale or lacks `activate-runtime`,
report that source is repaired but installed runtime is not activated; do not
treat that as a source implementation failure.

- [ ] **Step 7: Inspect residue**

```bash
find plugins/turbo-mode/ticket -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected: no new generated residue from this work. Existing unrelated residue should be reported rather than silently removed unless cleanup is in scope.

- [ ] **Step 8: Final diff review**

```bash
git diff --stat
git status --short --untracked-files=all -- \
  docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md \
  plugins/turbo-mode/ticket \
  .codex/ticket-runtime-proof.json \
  .codex/ticket-runtime-proof.candidate.json \
  .codex/ticket-runtime-smoke
git status --short --ignored --untracked-files=all -- \
  .codex/ticket-runtime-proof.json \
  .codex/ticket-runtime-proof.candidate.json \
  .codex/ticket-runtime-smoke
git diff -- plugins/turbo-mode/ticket docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md
```

Expected: diff and status match this plan, include no installed-cache mutation,
and expose any untracked source/test files or local activation artifacts before
commit. Source/test files that belong to the implementation must be staged;
local `.codex/ticket-runtime-*` artifacts must remain unstaged and be reported.

- [ ] **Step 9: Final commit**

```bash
git add \
  docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_stage_models.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture_agent.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_update_agent.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git commit -m "feat(ticket): activate runtime readiness gate"
```

Expected: coherent final implementation commit if earlier commit boundaries were not used. Prefer the earlier commit boundaries unless the user requests a single final commit.

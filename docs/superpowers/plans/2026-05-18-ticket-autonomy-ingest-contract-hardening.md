# Ticket Autonomy And Ingest Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ticket's autonomy, ingest, and temporary-payload contracts match the May 18 design decisions without adding locking, queueing, or activation-capable runtime readiness in this slice.

**Architecture:** Keep the existing capture/update/engine runner architecture, and narrow the supported high-level mutation contract to exactly three surfaces: `capture`, `update`, and `ingest`. Harden docs and tests around single-writer autonomy, the current guarded provenance/trust model, the DeferredWorkEnvelope consume contract, `stale_plan`, processed-envelope idempotency, and `.codex/ticket-tmp/` payload lifecycle. Runtime readiness remains future work; this plan does not add a readiness cache writer, app-server inventory producer, live hook smoke, or execute readiness gate.

**Tech Stack:** Python >=3.11, pytest, fenced-YAML Markdown tickets, JSON DeferredWorkEnvelope files, bytecode-safe `uv run` verification.

---

## Decision Freeze

These decisions are frozen for this implementation. Do not reopen them during execution unless a live source invariant makes the plan impossible; if that happens, stop and report the invariant before patching around it.

| Area | Frozen decision |
| --- | --- |
| Writer model | Ticket is single-writer for now. Do not add file locking, a queue, daemon coordination, or stronger serialization in this slice. |
| Parallel trigger | The future locking/queueing work becomes required when any workflow intentionally launches two or more ticket-capable agents in the same Codex session, or before enabling `auto_audit` for delegated multi-agent work. |
| Future parallel tracking | Add a tracked repo ticket tied to that operational trigger. |
| Supported mutation surfaces | Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`. `capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets. |
| `ticket_workflow.py` | Keep `ticket_workflow.py` as a compatibility/debug runner with tests. Remove any user-facing implication that it is a normal mutation interface. |
| Ingest ownership | Ticket owns the DeferredWorkEnvelope input contract, validation, idempotency behavior, duplicate handling, and processed-envelope lifecycle. Handoff owns emission. |
| Guard failure mode | Keep the Bash hook fail-open at the top level so ordinary Bash is not globally blocked by hook crashes. |
| Current `auto_audit` boundary | Current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model: hook-injected payload fields, matching `hook_request_origin`, non-empty `session_id`, live autonomy config re-read, and the current engine trust checks. |
| Activation readiness scope | This slice does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, does not add runtime inventory diagnostics, and does not add a new execute readiness gate. Stronger installed-runtime readiness is tracked as future work. |
| Future activation trigger | Activation-capable runtime readiness must land before any stronger trust claim or delegated multi-agent `auto_audit` rollout. |
| Payload lifecycle | Successful capture/update `execute` deletes its consumed prepare payload only when that payload is under `<PROJECT_ROOT>/.codex/ticket-tmp/`. Failed execute leaves the payload for debugging. |
| Payload doctor | `ticket_doctor` reports stale `.codex/ticket-tmp/` payloads and can clean them only through an explicit confirmed command after a TTL. Implementation default stale-payload TTL: 24 hours. |
| TOCTOU code | `stale_plan` is the single public machine-readable error code for TOCTOU/fingerprint conflicts. `toctou_conflict` may appear only as explanatory prose. |
| Ingest idempotency | The envelope id is the idempotency key. In current v1.0, the envelope id is the filename inside `docs/tickets/.envelopes/` because the JSON schema has no `id` field. |
| Processed replay | If the envelope id already exists in `.processed/`, ingest creates no ticket, reports a duplicate/replay outcome, preserves the incoming envelope, and leaves the existing processed record as authority. |
| Similar duplicates | Similar-content envelopes with different ids may be flagged through normal deduplication, but must not be auto-collapsed without a stable external key. |
| Processed retention | Processed envelopes are retained indefinitely for now as the idempotency ledger and cross-plugin audit trail. Retention/pruning is future policy work. |

## Non-Goals

- Do not implement file locking, queueing, or multi-writer serialization.
- Do not add app-server runtime inventory capture.
- Do not add live hook-mediated smoke tests.
- Do not add runtime-readiness diagnostic files.
- Do not write or validate `.codex/ticket-runtime-proof.json`.
- Do not gate `engine_execute()` on a runtime-readiness artifact.
- Do not mutate `/Users/jp/.codex/plugins/cache`, install plugins, refresh cache, or claim installed-runtime success from source changes.
- Do not implement `auto_silent`.
- Do not remove `ticket_workflow.py` or its test coverage.
- Do not make `ticket_workflow.py` user-facing.
- Do not change ordinary non-ticket Bash behavior.
- Do not prune processed envelopes.

## Source Files To Read First

Before implementation, re-read these live files. Historical handoffs, this plan, and prior reviews are not substitutes for current source truth.

- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/PRIVACY.md`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- `plugins/turbo-mode/ticket/scripts/ticket_envelope.py`
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- `plugins/turbo-mode/ticket/scripts/ticket_paths.py`
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- `plugins/turbo-mode/handoff/turbo_mode_handoff_runtime/defer.py`
- `plugins/turbo-mode/handoff/skills/defer/SKILL.md`

## File Structure

- `docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md` - this plan.
- `docs/tickets/2026-05-18-serialize-parallel-agent-ticket-creation.md` - new future-work ticket for the operational parallel-agent trigger.
- `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md` - new future-work ticket for app-server inventory, live installed hook smoke, nonce correlation, installed-cache execution binding, and activation proof write rules.
- `.gitignore` - ignore project-local `.codex/ticket-tmp/` payload residue.
- `plugins/turbo-mode/ticket/README.md` - public supported-surface, single-writer, current `auto_audit`, ingest, `stale_plan`, and retention wording.
- `plugins/turbo-mode/ticket/HANDBOOK.md` - operator-facing supported-surface, current `auto_audit`, `stale_plan`, ingest, and payload cleanup wording.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - contract-level supported-surface, current `auto_audit`, DeferredWorkEnvelope idempotency, and processed-retention wording.
- `plugins/turbo-mode/ticket/PRIVACY.md` - processed-envelope indefinite retention disclosure.
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` - operator skill contract for stale-payload diagnostics and confirmed cleanup.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - engine docstring clarification, ingest replay check before ticket creation, and replay response data.
- `plugins/turbo-mode/ticket/scripts/ticket_envelope.py` - envelope id and processed-path helper functions.
- `plugins/turbo-mode/ticket/scripts/ticket_payloads.py` - new helper for `.codex/ticket-tmp/` containment, successful payload deletion, stale-payload scan, and confirmed stale cleanup.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - delete successful capture execute payloads under `.codex/ticket-tmp/`; preserve failed execute payloads.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - delete successful update execute payloads under `.codex/ticket-tmp/`; preserve failed execute payloads.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - add stale-payload reporting and confirmed cleanup commands.
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py` - include stale `.codex/ticket-tmp/` payloads in doctor diagnostics and remove project-root fallback from doctor reporting.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` - static assertions for supported surfaces, current `auto_audit`, `stale_plan`, ingest idempotency, retention, ignored payload path, and doctor cleanup docs.
- `plugins/turbo-mode/ticket/tests/test_hook.py` - source-local hook allowlist and trust-field injection coverage for `ingest`.
- `plugins/turbo-mode/ticket/tests/test_envelope.py` - envelope id and processed-path helper tests.
- `plugins/turbo-mode/ticket/tests/test_ingest.py` - processed replay, mandatory replay outcome fields, incoming-envelope preservation, and different-id duplicate behavior tests.
- `plugins/turbo-mode/ticket/tests/test_capture.py` - successful and failed capture payload lifecycle tests.
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py` - successful and failed update payload lifecycle tests.
- `plugins/turbo-mode/ticket/tests/test_doctor.py` - stale-payload reporting and confirmed cleanup tests.
- `plugins/turbo-mode/handoff/tests/test_defer.py` and `plugins/turbo-mode/handoff/tests/test_cli_commands.py` - update only if Ticket's filename-id contract requires Handoff test wording or filename guarantees.

## Verification Harness

Baseline and focused Ticket tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Handoff bridge checks only if Handoff emission or defer docs change:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_defer.py tests/test_cli_commands.py tests/test_skill_docs.py -q
```

Changed-path lint is specified in Task 5 with the exact planned Python paths.

Whitespace gate:

```bash
git diff --check
```

## Stop Conditions

- If any implementation step starts writing, validating, or gating on `.codex/ticket-runtime-proof.json`, stop. That belongs to the future activation-readiness ticket.
- If any implementation step adds app-server runtime inventory, live hook smoke, runtime-readiness diagnostics, or an execute readiness gate, stop and move that work to the future activation-readiness ticket.
- If implementation needs to describe current `auto_audit` as stronger than the existing guarded provenance/trust model, stop and correct the docs.
- If production doctor root validation must be weakened to make stale-payload tests pass, stop. Stale-payload reporting should depend on project-root discovery and `.codex/ticket-tmp/` containment, not broader doctor root trust.
- If project root discovery fails at the runner, capture/update execute, or doctor boundary, stop and return an explicit policy error. Do not infer the project root with `tickets_dir.parent.parent`.
- If ingest cannot become idempotent before ticket creation, stop. Do not accept a design that creates a ticket and only then discovers the processed envelope already exists.
- If adding an envelope JSON `id` field becomes necessary, stop and split Handoff emission compatibility into a separate explicit contract-change slice. The current plan treats the v1.0 filename as the envelope id.
- If successful payload cleanup would delete files outside `<PROJECT_ROOT>/.codex/ticket-tmp/`, stop and constrain the cleanup helper.
- If stale-payload scan or cleanup follows a `.codex/ticket-tmp` symlink outside `PROJECT_ROOT`, stop. Resolve the temp directory first and fail closed on containment escape.
- If generated residue appears in plugin source paths (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.DS_Store`), clean it with `trash` only if cleanup is in scope, or report it as a blocker.

## Commit Boundaries

- Commit 1: this plan only.
- Commit 2: docs/tests freezing supported surfaces, single-writer autonomy, current `auto_audit`, `stale_plan`, and ingest contract wording.
- Commit 3: ingest idempotency, processed replay behavior, and envelope contract tests.
- Commit 4: capture/update payload cleanup and doctor stale-payload reporting/cleanup.
- Commit 5: future-work tickets for parallel autonomous creation and activation-capable runtime readiness, final docs alignment, and verification cleanup.

---

### Task 0: Baseline And Plan Authority

**Files:**
- Commit: `docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch and dirty state recorded. Preserve unrelated dirty work.

- [ ] **Step 2: Enforce branch gate before commits**

```bash
git branch --show-current
```

Expected: current branch is recorded. If the output is `main`, create the implementation branch before source edits or commits:

```bash
git switch -c fix/ticket-autonomy-ingest-contract-hardening
```

Expected: branch is `fix/ticket-autonomy-ingest-contract-hardening`. If already on a non-`main` task branch, continue on that branch and record the branch name in the task notes.

- [ ] **Step 3: Run the current Ticket baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: current Ticket test status captured before source edits. If this fails, classify baseline failures before changing source.

- [ ] **Step 4: Commit the plan if the user asks for a committed control document**

```bash
git add docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md
git commit -m "docs: plan ticket autonomy ingest hardening"
```

Expected: only this plan is staged and committed.

---

### Task 1: Freeze The Public Contract In Docs And Static Tests

**Files:**
- Modify: `.gitignore`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/PRIVACY.md`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`

- [ ] **Step 1: Add failing static docs tests**

Add these helpers and tests to `plugins/turbo-mode/ticket/tests/test_docs_contract.py`:

```python
ENGINE_RUNNER = PLUGIN_ROOT / "scripts" / "ticket_engine_runner.py"


def test_readme_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "README.md")

    assert "Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`." in text
    assert "`capture` and `update` use their preview-first prepare/execute wrappers." in text
    assert "`ingest`: `ticket_engine_user.py ingest <payload_file>` or `ticket_engine_agent.py ingest <payload_file>`" in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "They are not normal user-facing mutation interfaces" in text
    assert "`ticket_workflow.py` is a compatibility/debug runner" in text
    assert "`ticket_workflow.py` is not a supported user-facing mutation surface" in text


def test_handbook_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")

    assert "Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`." in text
    assert "`ingest` uses the guarded engine entrypoints" in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "`ticket_workflow.py` is a compatibility/debug runner" in text
    assert "not normal user-facing mutation interfaces" in text


def test_contract_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")

    assert "Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`." in text
    assert "`ingest` uses the guarded engine entrypoints" in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "must not be documented as the preferred way to create or mutate tickets" in text


def test_engine_docs_state_runner_is_not_public_mutation_surface() -> None:
    text = _read_text(ENGINE_RUNNER)

    assert "This module is never invoked directly." in text
    assert "The public guarded engine entrypoints are ticket_engine_user.py and ticket_engine_agent.py." in text
    assert "Direct engine stages are low-level compatibility, debug, and agent-internal paths." in text
    assert "not normal user-facing mutation interfaces" in text


def test_docs_describe_current_auto_audit_boundary_without_activation_readiness() -> None:
    readme = _read_text(PLUGIN_ROOT / "README.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    for text in [readme, handbook, contract]:
        assert "Current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model" in text
        assert "hook-injected payload fields" in text
        assert "matching `hook_request_origin`" in text
        assert "This slice does not add activation-capable runtime readiness" in text
        assert "does not write `.codex/ticket-runtime-proof.json`" in text
        assert "does not add a new execute readiness gate" in text
        assert "live app-server inventory and live hook-mediated smoke" in text


def test_stale_plan_is_only_public_toctou_error_code() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read_text(path)
        normalized = _normalize_whitespace(text).lower()
        assert "error_code: toctou_conflict" not in normalized
        assert "error code `toctou_conflict`" not in normalized
        assert "blocked with a `toctou_conflict` error" not in normalized
        assert "| `toctou_conflict`" not in text
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    assert "`stale_plan`" in contract
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "`toctou_conflict` is descriptive prose only, not a public error code." in handbook


def test_ingest_contract_documents_filename_id_and_indefinite_processed_retention() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    privacy = _read_text(PLUGIN_ROOT / "PRIVACY.md")
    assert "For v1.0, the envelope id is the envelope filename" in contract
    assert "Processed envelopes are retained indefinitely" in contract
    assert "duplicate/replay" in contract
    assert "preserves the incoming envelope" in contract
    assert "Processed envelopes are retained indefinitely" in privacy


def test_project_local_ticket_tmp_payloads_are_ignored() -> None:
    gitignore = _read_text(PLUGIN_ROOT.parents[2] / ".gitignore")

    assert ".codex/ticket-tmp/" in gitignore
```

Update existing tests that currently reject all `ticket_workflow.py prepare` and `ticket_workflow.py execute` prose in `HANDBOOK.md` so they reject only preferred-surface wording. Use this replacement assertion shape:

```python
normalized_handbook = _normalize_whitespace(_read_text(PLUGIN_ROOT / "HANDBOOK.md")).lower()
assert "preferred way to create or mutate tickets" not in normalized_handbook
assert "ticket_workflow.py is a compatibility/debug runner" in normalized_handbook
```

Add these source-local hook tests to `plugins/turbo-mode/ticket/tests/test_hook.py` so `ingest` is proven as a guarded source surface without adding installed-runtime smoke:

```python
def test_hook_allows_ticket_engine_ingest_and_injects_payload(tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps(
            {
                "tickets_dir": "docs/tickets",
                "envelope_path": "docs/tickets/.envelopes/2026-05-18T120000Z-test.json",
            }
        ),
        encoding="utf-8",
    )
    event = make_hook_input(
        f"python3 -B {plugin_root}/scripts/ticket_engine_user.py ingest {payload}",
        plugin_root=str(plugin_root),
        cwd=str(tmp_path),
        session_id="session-hook",
    )

    result = run_hook(event, plugin_root=str(plugin_root))

    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    injected = json.loads(payload.read_text(encoding="utf-8"))
    assert injected["session_id"] == "session-hook"
    assert injected["hook_injected"] is True
    assert injected["hook_request_origin"] == "user"
```

Update `TestAllowlist.test_allows_all_valid_subcommands` so the loop includes `ingest`:

```python
for subcommand in ("classify", "plan", "preflight", "execute", "ingest"):
    payload_file = make_payload_file(tmp_path, {"action": subcommand})
    inp = make_hook_input(
        f"python3 {plugin_root}/scripts/ticket_engine_user.py {subcommand} {payload_file}",
        plugin_root=plugin_root,
    )
    output = run_hook(inp, plugin_root=plugin_root)
    assert _decision(output) == "allow", f"Failed for subcommand: {subcommand}"
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_hook.py -q
```

Expected: new docs tests fail because docs have not been updated; new hook tests fail if `ingest` is missing from the source hook allowlist or trust-field injection path.

- [ ] **Step 2: Ignore project-local Ticket temporary payloads**

Add this root `.gitignore` entry if an equivalent entry does not already exist:

```gitignore
.codex/ticket-tmp/
```

`.codex/ticket-tmp/` contains project-local prepare payloads and is not source-authority state.

- [ ] **Step 3: Update `README.md` contract wording**

Add a short "Supported Mutation Surfaces" subsection near the current skill-backed operations table:

```markdown
Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`.

- `capture`: `ticket_capture.py prepare` then `ticket_capture.py execute`
- `update`: `ticket_update.py prepare` then `ticket_update.py execute`
- `ingest`: `ticket_engine_user.py ingest <payload_file>` or `ticket_engine_agent.py ingest <payload_file>`, consuming a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`

`capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets.

`ticket_workflow.py` is a compatibility/debug runner kept for tests and low-level recovery work. `ticket_workflow.py` is not a supported user-facing mutation surface.
```

In "Autonomy Policy", add:

```markdown
`auto_audit` is single-writer. Do not intentionally launch two or more ticket-capable agents in the same Codex session. The operational trigger for future locking/queueing work is: any workflow intentionally launches two or more ticket-capable agents in the same Codex session, or `auto_audit` is enabled for delegated multi-agent work.
```

In "Agent Integration", add the current-boundary caveat:

```markdown
Current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model: hook-injected payload fields, matching `hook_request_origin`, non-empty `session_id`, live autonomy config re-read, and the current engine trust checks. This slice does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, and does not add a new execute readiness gate. Stronger installed-runtime readiness, including live app-server inventory and live hook-mediated smoke, is future work and must land before any stronger trust claim or delegated multi-agent `auto_audit` rollout.
```

In known limitations, replace broad parallel-safety wording with single-writer wording.

- [ ] **Step 4: Update `HANDBOOK.md` operational wording**

Make the failure matrix and internals say:

- The TOCTOU/fingerprint recovery code is `stale_plan`.
- `toctou_conflict` is descriptive prose only, not a public error code.
- Current agent-origin `auto_audit` execute remains governed by hook-injected payload fields, matching `hook_request_origin`, non-empty `session_id`, live autonomy config re-read, and current engine trust checks.
- This slice does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, and does not add a new execute readiness gate.
- Stronger installed-runtime readiness, including live app-server inventory and live hook-mediated smoke, is future work.
- Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`.
- `ingest` uses `ticket_engine_user.py ingest <payload_file>` or `ticket_engine_agent.py ingest <payload_file>` rather than direct `ticket_engine_runner.py` invocation.
- Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths, not normal user-facing mutation interfaces.
- `ticket_workflow.py` remains compatibility/debug only.

- [ ] **Step 5: Update `references/ticket-contract.md`**

Add this surface contract:

```markdown
Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`. `capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets.
```

Add this current `auto_audit` boundary:

```markdown
Current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model: hook-injected payload fields, matching `hook_request_origin`, non-empty `session_id`, live autonomy config re-read, and the current engine trust checks. This slice does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, and does not add a new execute readiness gate. Stronger installed-runtime readiness, including live app-server inventory and live hook-mediated smoke, is future work and must land before any stronger trust claim or delegated multi-agent `auto_audit` rollout.
```

Change DeferredWorkEnvelope section 11 to state:

```markdown
For v1.0, the envelope id is the envelope filename under `docs/tickets/.envelopes/`. Ticket owns this input contract and uses that id for idempotency.
```

Change storage retention to:

```markdown
- Processed: `docs/tickets/.envelopes/.processed/<filename>`
- Retention: processed envelopes are retained indefinitely for now as the idempotency ledger and cross-plugin audit trail.
```

Add consumer behavior:

```markdown
Before creating a ticket, ingest checks whether `.processed/<filename>` already exists. If it does, ingest returns a duplicate/replay outcome, preserves the incoming envelope, and creates no ticket. Similar-content envelopes with different filenames go through normal duplicate detection and are not auto-collapsed.
```

- [ ] **Step 6: Update `PRIVACY.md`**

Add one concise note:

```markdown
Processed DeferredWorkEnvelope files under `docs/tickets/.envelopes/.processed/` are retained indefinitely for now as the idempotency ledger and cross-plugin audit trail. They may contain deferred-work metadata such as source session references, problem statements, acceptance criteria, and file paths.
```

- [ ] **Step 7: Update engine docstring**

Modify the module docstring in `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` so it contains this text:

```python
"""Shared entrypoint runner for the ticket engine.

Consolidates boundary logic (payload read, origin enforcement, trust triple,
project root, tickets_dir, dispatch, exit codes) that was previously
duplicated between ticket_engine_user.py and ticket_engine_agent.py.

Entrypoints import and call run() with their hardcoded request_origin.
This module is never invoked directly. The public guarded engine entrypoints
are ticket_engine_user.py and ticket_engine_agent.py. Direct engine stages are
low-level compatibility, debug, and agent-internal paths. They are not normal
user-facing mutation interfaces.
"""
```

- [ ] **Step 8: Re-run docs tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
```

Expected: docs contract tests pass.

---

### Task 2: Make Ingest Idempotent Before Ticket Creation

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_envelope.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_envelope.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ingest.py`

- [ ] **Step 1: Add failing envelope helper tests**

Add these tests to `plugins/turbo-mode/ticket/tests/test_envelope.py`:

```python
def test_envelope_id_from_path_uses_filename(tmp_path: Path) -> None:
    from scripts.ticket_envelope import envelope_id_from_path

    envelope_path = tmp_path / "docs" / "tickets" / ".envelopes" / "2026-05-18T120000Z-demo.json"

    assert envelope_id_from_path(envelope_path) == "2026-05-18T120000Z-demo.json"


def test_processed_path_for_envelope_uses_processed_subdirectory(tmp_path: Path) -> None:
    from scripts.ticket_envelope import processed_path_for_envelope

    envelope_path = tmp_path / "docs" / "tickets" / ".envelopes" / "demo.json"

    assert processed_path_for_envelope(envelope_path) == envelope_path.parent / ".processed" / "demo.json"
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_envelope.py::test_envelope_id_from_path_uses_filename tests/test_envelope.py::test_processed_path_for_envelope_uses_processed_subdirectory -q
```

Expected: fails because helper functions do not exist.

- [ ] **Step 2: Add envelope helper functions**

Add these functions to `plugins/turbo-mode/ticket/scripts/ticket_envelope.py` above `move_to_processed()`:

```python
def envelope_id_from_path(envelope_path: Path) -> str:
    """Return the v1.0 DeferredWorkEnvelope id.

    The v1.0 JSON schema has no id field; the filename under
    docs/tickets/.envelopes/ is the durable idempotency key.
    """
    return envelope_path.name


def processed_path_for_envelope(envelope_path: Path) -> Path:
    """Return the processed ledger path for a DeferredWorkEnvelope filename."""
    return envelope_path.parent / ".processed" / envelope_id_from_path(envelope_path)
```

Update `move_to_processed()` to use `processed_path_for_envelope(envelope_path)` for `dest`.

- [ ] **Step 3: Add failing processed replay tests**

Add this test to `plugins/turbo-mode/ticket/tests/test_ingest.py`:

```python
def test_processed_filename_replay_reports_duplicate_without_creating_ticket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    envelopes_dir = tickets_dir / ".envelopes"
    envelopes_dir.mkdir(parents=True)
    processed_dir = envelopes_dir / ".processed"
    processed_dir.mkdir()

    envelope_path = envelopes_dir / "2026-05-18T120000Z-replay.json"
    envelope_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
    processed_path = processed_dir / envelope_path.name
    processed_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    payload = {
        "envelope_path": str(envelope_path),
        "tickets_dir": str(tickets_dir),
        "session_id": "test-session",
        "hook_injected": True,
        "hook_request_origin": "user",
    }
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = run("user", argv=["ingest", str(payload_file)], prog="test")
    captured = capsys.readouterr()
    response = json.loads(captured.out)

    assert exit_code == 0
    assert response["state"] == "ok"
    assert response["data"]["ingest_outcome"] == "duplicate_replay"
    assert response["data"]["envelope_id"] == envelope_path.name
    assert response["data"]["processed_path"] == str(processed_path)
    assert response["data"]["incoming_envelope_path"] == str(envelope_path)
    assert response["data"]["ticket_created"] is False
    assert envelope_path.exists()
    assert processed_path.exists()
    assert not list(tickets_dir.glob("*.md"))
```

Add this test to prove content-similar envelopes with different ids do not replay-collapse when only an older `.processed/<old-id>.json` exists:

```python
def test_same_content_different_envelope_id_is_not_processed_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    envelopes_dir = tickets_dir / ".envelopes"
    processed_dir = envelopes_dir / ".processed"
    processed_dir.mkdir(parents=True)
    processed_path = processed_dir / "old-id.json"
    processed_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

    envelope_path = envelopes_dir / "new-id.json"
    envelope_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
    payload = {
        "envelope_path": str(envelope_path),
        "tickets_dir": str(tickets_dir),
        "session_id": "test-session",
        "hook_injected": True,
        "hook_request_origin": "user",
    }
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = run("user", argv=["ingest", str(payload_file)], prog="test")
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert response["state"] == "ok_create"
    assert response["data"]["ingest_outcome"] == "created"
    assert response["data"]["envelope_id"] == envelope_path.name
    assert response["data"]["ticket_created"] is True
    assert not envelope_path.exists()
    assert processed_path.exists()
    assert (processed_dir / envelope_path.name).exists()
    assert len(list(tickets_dir.glob("*.md"))) == 1
```

Add this test to prove `duplicate_candidate` still comes from real existing tickets, not from processed-envelope history alone:

```python
def test_same_content_different_envelope_id_duplicate_candidate_requires_existing_ticket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    envelopes_dir = tickets_dir / ".envelopes"
    envelopes_dir.mkdir(parents=True)

    first_envelope = envelopes_dir / "old-id.json"
    first_envelope.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
    first_payload = {
        "envelope_path": str(first_envelope),
        "tickets_dir": str(tickets_dir),
        "session_id": "test-session",
        "hook_injected": True,
        "hook_request_origin": "user",
    }
    first_payload_file = tmp_path / "payload1.json"
    first_payload_file.write_text(json.dumps(first_payload), encoding="utf-8")
    assert run("user", argv=["ingest", str(first_payload_file)], prog="test") == 0
    capsys.readouterr()

    second_envelope = envelopes_dir / "new-id.json"
    second_envelope.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
    second_payload = {
        "envelope_path": str(second_envelope),
        "tickets_dir": str(tickets_dir),
        "session_id": "test-session",
        "hook_injected": True,
        "hook_request_origin": "user",
    }
    second_payload_file = tmp_path / "payload2.json"
    second_payload_file.write_text(json.dumps(second_payload), encoding="utf-8")

    exit_code = run("user", argv=["ingest", str(second_payload_file)], prog="test")
    response = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert response["state"] == "duplicate_candidate"
    assert response.get("data", {}).get("ingest_outcome") != "duplicate_replay"
    assert second_envelope.exists()
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ingest.py -q
```

Expected: processed filename replay test fails because `_dispatch_ingest()` still creates or attempts a ticket before checking `.processed/<filename>`.

- [ ] **Step 4: Implement replay check before reading or creating**

Modify `_dispatch_ingest()` in `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`:

```python
    from scripts.ticket_envelope import (
        envelope_id_from_path,
        map_envelope_to_fields,
        move_to_processed,
        processed_path_for_envelope,
        read_envelope,
    )
```

After the containment check and after rejecting direct `.processed` input paths, add:

```python
    envelope_id = envelope_id_from_path(envelope_path)
    processed_path = processed_path_for_envelope(envelope_path)
    if processed_path.exists():
        return EngineResponse(
            state="ok",
            message=f"duplicate/replay: envelope {envelope_id} already processed",
            data={
                "ingest_outcome": "duplicate_replay",
                "envelope_id": envelope_id,
                "processed_path": str(processed_path),
                "incoming_envelope_path": str(envelope_path),
                "ticket_created": False,
            },
        )
```

After a successful non-replay move to processed, add ingest outcome data while preserving existing response data:

```python
    data = dict(exec_resp.data or {})
    data.update(
        {
            "ingest_outcome": "created",
            "envelope_id": envelope_id,
            "processed_path": str(processed_path_for_envelope(envelope_path)),
            "incoming_envelope_path": str(envelope_path),
            "ticket_created": True,
        }
    )
    return EngineResponse(
        state=exec_resp.state,
        message=exec_resp.message,
        ticket_id=exec_resp.ticket_id,
        data=data,
    )
```

If the move fails after ticket creation, keep the existing non-fatal reporting behavior and add `"ingest_outcome": "created_envelope_move_failed"` plus `"ticket_created": True` in `data`.

- [ ] **Step 5: Run ingest and envelope tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_envelope.py tests/test_ingest.py -q
```

Expected: envelope helper and ingest replay tests pass. Replay by filename exits `0`, creates no ticket, preserves the incoming envelope, and reports `ingest_outcome: duplicate_replay`.

---

### Task 3: Clean Successful Capture/Update Payloads And Report Stale Payloads

**Files:**
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Create: `plugins/turbo-mode/ticket/scripts/ticket_payloads.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_capture.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_doctor.py`

- [ ] **Step 1: Add failing payload helper tests through capture/update flows**

Add tests to `plugins/turbo-mode/ticket/tests/test_capture.py` that use the existing capture helpers in that file:

```python
def test_successful_capture_execute_deletes_ticket_tmp_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / ".codex" / "ticket-tmp" / "capture.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(
        json.dumps(
            {
                "capture": {
                    "captured_request": "Track timeout cleanup",
                    "title": "Track timeout cleanup",
                    "problem": "Timeout cleanup needs tracking.",
                    "next_action": "Review timeout cleanup.",
                },
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
                "tickets_dir": "docs/tickets",
            }
        ),
        encoding="utf-8",
    )

    prepare = run_capture("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    execute = run_capture("execute", payload_path)

    assert execute["state"] == "ok_create"
    assert not payload_path.exists()
```

Add a failed-execute preservation test in the same file:

```python
def test_failed_capture_execute_preserves_ticket_tmp_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    payload_path = tmp_path / ".codex" / "ticket-tmp" / "capture.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(json.dumps({"tickets_dir": "docs/tickets"}), encoding="utf-8")

    execute = run_capture("execute", payload_path)

    assert execute["state"] in {"preflight_failed", "policy_blocked", "escalate"}
    assert payload_path.exists()
```

Add equivalent tests to `plugins/turbo-mode/ticket/tests/test_update_refinement.py` using that file's existing `_make_refinement_ticket()`, `_payload()`, and `run_update()` helpers:

```python
def test_successful_update_execute_deletes_ticket_tmp_payload(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    _make_refinement_ticket(tmp_tickets)
    payload_path = project_root / ".codex" / "ticket-tmp" / "update.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(
        json.dumps(_payload(tmp_tickets, {"priority": "high"})),
        encoding="utf-8",
    )

    prepare = run_update("prepare", payload_path)
    assert prepare["state"] == "ready_to_execute"
    execute = run_update("execute", payload_path)

    assert execute["state"] == "ok_update"
    assert not payload_path.exists()
```

```python
def test_failed_update_execute_preserves_ticket_tmp_payload(
    tmp_tickets: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = project_root / ".codex" / "ticket-tmp" / "update.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_text(json.dumps({"tickets_dir": str(tmp_tickets)}), encoding="utf-8")

    execute = run_update("execute", payload_path)

    assert execute["state"] in {"preflight_failed", "policy_blocked", "escalate"}
    assert payload_path.exists()
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_capture.py tests/test_update_refinement.py -q
```

Expected: new success tests fail because payload files remain after successful execute.

- [ ] **Step 2: Add `ticket_payloads.py`**

Create `plugins/turbo-mode/ticket/scripts/ticket_payloads.py`:

```python
"""Lifecycle helpers for project-local Ticket prepare payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_STALE_PAYLOAD_TTL = timedelta(hours=24)


class TicketPayloadPathError(ValueError):
    """Raised when a Ticket payload path escapes the project-local temp root."""


@dataclass(frozen=True)
class StalePayload:
    path: Path
    age_seconds: int
    size_bytes: int
    modified_at: str


def ticket_tmp_dir(project_root: Path) -> Path:
    """Return the project-local Ticket temporary payload directory."""
    return project_root / ".codex" / "ticket-tmp"


def resolved_ticket_tmp_dir(project_root: Path) -> Path:
    """Return the resolved temp directory, rejecting symlink escapes from project_root."""
    resolved_project = project_root.resolve()
    resolved_tmp = ticket_tmp_dir(project_root).resolve()
    try:
        resolved_tmp.relative_to(resolved_project)
    except ValueError as exc:
        raise TicketPayloadPathError(
            "ticket tmp directory containment failed: resolved temp directory "
            f"is outside project root. Got: {str(resolved_tmp)!r:.100}"
        ) from exc
    return resolved_tmp


def is_ticket_tmp_payload(payload_path: Path, project_root: Path) -> bool:
    """Return True when payload_path resolves under project_root/.codex/ticket-tmp."""
    try:
        payload_path.resolve().relative_to(resolved_ticket_tmp_dir(project_root))
    except (OSError, ValueError, TicketPayloadPathError):
        return False
    return True


def delete_consumed_payload(payload_path: Path, project_root: Path) -> bool:
    """Delete a consumed prepare payload only inside project_root/.codex/ticket-tmp."""
    if not is_ticket_tmp_payload(payload_path, project_root):
        return False
    try:
        payload_path.resolve().unlink()
    except FileNotFoundError:
        return False
    return True


def stale_payloads(
    project_root: Path,
    *,
    now: datetime | None = None,
    stale_after: timedelta = DEFAULT_STALE_PAYLOAD_TTL,
) -> list[StalePayload]:
    """Return stale JSON payloads under project_root/.codex/ticket-tmp."""
    current = now or datetime.now(UTC)
    root = resolved_ticket_tmp_dir(project_root)
    if not root.is_dir():
        return []
    stale: list[StalePayload] = []
    for path in sorted(root.glob("*.json")):
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        age = current - modified
        if age < stale_after:
            continue
        stale.append(
            StalePayload(
                path=path,
                age_seconds=int(age.total_seconds()),
                size_bytes=stat.st_size,
                modified_at=modified.isoformat(),
            )
        )
    return stale


def clean_stale_payloads(
    project_root: Path,
    *,
    now: datetime | None = None,
    stale_after: timedelta = DEFAULT_STALE_PAYLOAD_TTL,
) -> list[StalePayload]:
    """Delete stale JSON payloads under project_root/.codex/ticket-tmp and return deletions."""
    stale = stale_payloads(project_root, now=now, stale_after=stale_after)
    for item in stale:
        item.path.unlink()
    return stale
```

- [ ] **Step 3: Wire successful cleanup into capture execute**

Modify `plugins/turbo-mode/ticket/scripts/ticket_capture.py` imports:

```python
from scripts.ticket_payloads import delete_consumed_payload  # noqa: E402
```

In `_execute()`, after stale-plan checks pass and before `dispatch_stage("execute", payload, tickets_dir, request_origin)`, discover the project root through the existing helper and fail closed if absent:

```python
    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        return _response(
            "policy_blocked",
            "Cannot determine project root for payload cleanup: no .codex/ or .git/ marker found",
            error_code="policy_blocked",
        )
```

After the `response = _engine_response_to_dict(dispatch_stage("execute", payload, tickets_dir, request_origin))` call, delete only after success:

```python
    if response.get("state") == "ok_create":
        try:
            response.setdefault("data", {})["payload_deleted"] = delete_consumed_payload(
                payload_path,
                project_root,
            )
        except OSError as exc:
            response.setdefault("data", {})["payload_cleanup_error"] = str(exc)
    return response
```

- [ ] **Step 4: Wire successful cleanup into update execute**

Modify `plugins/turbo-mode/ticket/scripts/ticket_update.py` imports:

```python
from scripts.ticket_payloads import delete_consumed_payload  # noqa: E402
```

In `_execute()`, after stale-plan checks pass and before `dispatch_stage("execute", payload, tickets_dir, request_origin)`, discover the project root through `discover_project_root(tickets_dir)` and return `policy_blocked` if absent.

After the existing preview preservation block, delete only after successful mutation:

```python
    if response.get("state") in {"ok_update", "ok_close", "ok_reopen"}:
        try:
            response.setdefault("data", {})["payload_deleted"] = delete_consumed_payload(
                payload_path,
                project_root,
            )
        except OSError as exc:
            response.setdefault("data", {})["payload_cleanup_error"] = str(exc)
    return response
```

- [ ] **Step 5: Add doctor docs and stale-payload tests**

Update `plugins/turbo-mode/ticket/tests/test_docs_contract.py` so the existing `test_ticket_doctor_skill_contract_is_explicit_maintenance_only()` also proves the confirmed cleanup contract:

```python
    assert "ticket_doctor.py clean-stale-payloads <TICKETS_DIR>" in text
    assert "ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads" in text
    assert "stale `.codex/ticket-tmp/` payloads" in text
    assert "24 hours" in text
    assert "ask before any cleanup mutation" in text
```

Add this docs contract test:

```python
def test_doctor_docs_describe_confirmed_stale_payload_cleanup() -> None:
    readme = _read_text(PLUGIN_ROOT / "README.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    skill = _read_text(DOCTOR_SKILL)
    for text in [readme, handbook, skill]:
        assert "diagnose reports stale `.codex/ticket-tmp/` payloads" in text
        assert "24 hours" in text
        assert "`ticket_doctor.py clean-stale-payloads <TICKETS_DIR>`" in text
        assert "`--confirm-clean-stale-payloads`" in text
```

Add these tests to `plugins/turbo-mode/ticket/tests/test_doctor.py`:

```python
def test_ticket_doctor_reports_stale_ticket_tmp_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    payload = payload_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    monkeypatch.chdir(tmp_path)

    plugin_root = Path(__file__).resolve().parents[1]
    report = ticket_doctor(tickets_dir, plugin_root=plugin_root, cache_root=plugin_root)

    assert report["payloads"]["tmp_dir"] == str(payload_dir)
    assert report["payloads"]["stale_count"] == 1
    assert report["payloads"]["stale"][0]["path"] == str(payload)
```

Add CLI cleanup tests:

```python
def test_ticket_doctor_clean_stale_payloads_requires_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    payload = payload_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    monkeypatch.chdir(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "clean-stale-payloads",
            str(tickets_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert payload.exists()
    assert "requires --confirm-clean-stale-payloads" in completed.stdout
```

```python
def test_ticket_doctor_clean_stale_payloads_deletes_only_with_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    payload = payload_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    monkeypatch.chdir(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "clean-stale-payloads",
            str(tickets_dir),
            "--confirm-clean-stale-payloads",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    response = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert response["state"] == "ok"
    assert response["data"]["deleted_count"] == 1
    assert not payload.exists()
```

Add a symlink escape test so the cleanup path fails closed if `.codex/ticket-tmp` resolves outside the project root:

```python
def test_ticket_doctor_clean_stale_payloads_rejects_symlink_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    external_dir = tmp_path.parent / f"{tmp_path.name}-external-ticket-tmp"
    external_dir.mkdir()
    payload = external_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "ticket-tmp").symlink_to(external_dir, target_is_directory=True)
    monkeypatch.chdir(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "clean-stale-payloads",
            str(tickets_dir),
            "--confirm-clean-stale-payloads",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert payload.exists()
    assert "containment failed" in (completed.stdout + completed.stderr)
```

Add missing imports if they are not already present:

```python
import os
import sys
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_doctor.py -q
```

Expected: new docs and stale-payload tests fail because doctor docs do not describe the cleanup command and doctor does not report or clean stale payloads yet.

- [ ] **Step 6: Add stale-payload reporting and cleanup**

Modify `plugins/turbo-mode/ticket/scripts/ticket_triage.py`:

- Import `DEFAULT_STALE_PAYLOAD_TTL`, `TicketPayloadPathError`, and `stale_payloads` from `scripts.ticket_payloads`.
- In `ticket_doctor()`, replace `project_root = discover_project_root(tickets_dir) or tickets_dir.parent.parent` with:

```python
    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        raise DoctorInputError(
            "doctor project_root failed: no .codex/ or .git/ marker found. "
            f"Got: {str(tickets_dir)!r:.100}"
        )
```

- Add this payload section to the returned report:

```python
        "payloads": {
            "tmp_dir": str(project_root / ".codex" / "ticket-tmp"),
            "stale_after_hours": int(DEFAULT_STALE_PAYLOAD_TTL.total_seconds() // 3600),
            "stale_count": len(stale_payload_rows),
            "stale": stale_payload_rows,
        },
```

Build `stale_payload_rows` immediately before the return and convert containment failures into an explicit doctor input error:

```python
    try:
        stale_payload_rows = [
            {
                "path": str(item.path),
                "age_seconds": item.age_seconds,
                "size_bytes": item.size_bytes,
                "modified_at": item.modified_at,
            }
            for item in stale_payloads(project_root)
        ]
    except TicketPayloadPathError as exc:
        raise DoctorInputError(str(exc)) from exc
```

Modify `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`:

- Import `TicketPayloadPathError` and `clean_stale_payloads`.
- Add `clean-stale-payloads` subcommand with `tickets_dir` and `--confirm-clean-stale-payloads`.
- Resolve the same project root as `_resolve_tickets_dir()` and fail closed if absent.
- Without confirmation, return exit `1` with message `stale payload cleanup requires --confirm-clean-stale-payloads`.
- With confirmation, delete stale payloads and return:

```python
_response(
    "ok",
    {
        "mode": "clean-stale-payloads",
        "deleted_count": len(deleted),
        "deleted": [str(item.path) for item in deleted],
    },
    "Deleted stale Ticket prepare payloads.",
)
```
- If cleanup raises `TicketPayloadPathError`, return a non-zero policy response and do not delete anything outside the project-local temp root.

Update user-facing doctor docs:

- In `plugins/turbo-mode/ticket/README.md`, state that `diagnose` reports stale `.codex/ticket-tmp/` payloads older than 24 hours and that cleanup uses `ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads`.
- In `plugins/turbo-mode/ticket/HANDBOOK.md`, add the same maintenance entry and clarify that stale-payload cleanup is TTL-scoped and confirmation-gated.
- In `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`, add a "Stale Payload Cleanup" section. It must run `diagnose` first, show the stale payload report, ask before any cleanup mutation, and only then run:

```bash
python3 -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads
```

- [ ] **Step 7: Run payload lifecycle and doctor tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_capture.py tests/test_update_refinement.py tests/test_doctor.py -q
```

Expected: doctor docs describe the cleanup surface, success payloads under `.codex/ticket-tmp/` are deleted, failed execute payloads remain, and doctor reports/cleans stale payloads only through the confirmed command.

---

### Task 4: Track Future Trust And Parallelism Triggers As Tickets

**Files:**
- Create: `docs/tickets/2026-05-18-serialize-parallel-agent-ticket-creation.md`
- Create: `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`

- [ ] **Step 1: Add the parallel autonomous creation future-work ticket**

Create `docs/tickets/2026-05-18-serialize-parallel-agent-ticket-creation.md`:

````markdown
# T-20260518-01: Serialize parallel autonomous ticket creation before delegated auto_audit

```yaml
id: T-20260518-01
date: "2026-05-18"
created_at: "2026-05-18T00:00:00Z"
status: open
priority: medium
effort: M
source:
  type: follow-up
  ref: ticket-autonomy-ingest-contract-hardening
  session: 2026-05-18-ticket-autonomy-ingest-contract-hardening
tags: [ticket, autonomy, concurrency, follow-up]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/ticket/scripts/ticket_engine_core.py, plugins/turbo-mode/ticket/scripts/ticket_capture.py, plugins/turbo-mode/ticket/scripts/ticket_update.py, plugins/turbo-mode/ticket/references/ticket-contract.md]
```

## Problem
Ticket is deliberately single-writer for autonomous creation in the current source slice. Adding file locking, queueing, or daemon coordination now would pay complexity before parallel autonomous ticket creation is a real near-term requirement.

The trigger is concrete: any workflow intentionally launches two or more ticket-capable agents in the same Codex session, or `auto_audit` is enabled for delegated multi-agent work.

## Acceptance Criteria
- [ ] The design chooses a serialization mechanism for parallel ticket-capable agents in one Codex session.
- [ ] The implementation protects ticket id allocation, audit writes, processed-envelope moves, and capture/update payload cleanup from parallel writes.
- [ ] Tests exercise two ticket-capable agents racing to create or ingest tickets.
- [ ] Docs state when parallel autonomous ticket creation is supported and which paths remain single-writer.
- [ ] Delegated multi-agent `auto_audit` rollout depends on this work and activation-capable runtime readiness.
````

- [ ] **Step 2: Add the activation-capable runtime readiness future-work ticket**

Create `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`:

````markdown
# T-20260518-02: Design and implement activation-capable Ticket runtime readiness

```yaml
id: T-20260518-02
date: "2026-05-18"
created_at: "2026-05-18T00:00:00Z"
status: open
priority: high
effort: L
source:
  type: follow-up
  ref: ticket-autonomy-ingest-contract-hardening
  session: 2026-05-18-ticket-autonomy-ingest-contract-hardening
tags: [ticket, autonomy, runtime-readiness, follow-up]
blocked_by: []
blocks: []
contract_version: "1.0"
key_file_paths: [plugins/turbo-mode/ticket/scripts/ticket_engine_core.py, plugins/turbo-mode/ticket/scripts/ticket_doctor.py, plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py, plugins/turbo-mode/ticket/references/ticket-contract.md]
```

## Problem
This source slice documents that current agent-origin `auto_audit` execute remains governed by the existing guarded provenance/trust model. It does not add activation-capable runtime readiness, does not write `.codex/ticket-runtime-proof.json`, and does not add a new execute readiness gate.

Before Ticket makes any stronger installed-runtime trust claim, or before delegated multi-agent `auto_audit` is rolled out, Ticket needs an activation-capable readiness boundary that proves the installed runtime path and the live hook-mediated mutation path.

## Trigger
- Before enabling `agent + auto_audit + execute` through runtime readiness.
- Before public docs, contracts, or status reports claim stronger installed-runtime readiness than the current guarded provenance/trust model.
- Before delegated multi-agent `auto_audit` rollout.

## Required Scope
- Ticket-owned app-server inventory producer for activation evidence.
- Activation-mode doctor command that performs live app-server inventory itself.
- Live installed Codex hook-mediated smoke inside activation-mode doctor.
- Run nonce correlation between inventory, hook smoke, and activation proof write.
- Installed cache identity and executing Ticket root identity checks.
- Structural separation between activation proof output and debug/external evidence.
- `engine_execute()` gate integration only after the activation producer is structurally correct.

## Hard Stop
No activation proof file can be written without live app-server inventory plus live installed hook-mediated smoke. External evidence, fixture transcripts, source-checkout diagnostics, and handwritten JSON must not be able to write or promote `.codex/ticket-runtime-proof.json`.

## Acceptance Criteria
- [ ] Activation mode starts and records a fresh app-server inventory covering plugin/read, plugin/list, skills/list, and schema-proven hook inventory.
- [ ] Activation mode runs a live installed hook-mediated smoke through Codex, not by invoking the hook script directly.
- [ ] The smoke records installed `PLUGIN_ROOT`, hook source/command, `session_id`, hook event, injected fields, nonce, Codex version, and outcome.
- [ ] The activation proof binds project root, Ticket plugin id/version, installed cache path, matched hook identity, exact guard command/script identity, and exactly one Bash PreToolUse guard.
- [ ] Source-checkout execution can inspect or explain installed readiness but cannot satisfy activation for `agent + auto_audit + execute`.
- [ ] External/debug evidence writes only non-activation diagnostics or stdout and cannot overwrite the activation proof path.
- [ ] `engine_execute()` gates only agent-origin ticket-capable execute surfaces after the activation producer and live smoke pass.
- [ ] Tests prove inventory-only, fixture-only, source-only, unavailable-smoke, and malformed-smoke paths do not activate autonomy.
````

- [ ] **Step 3: Verify tickets parse as tracked markdown tickets**

Run the source-local ticket read command used by the repo for local ticket listing. This is source-read evidence only, not hook/runtime proof:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket python scripts/ticket_read.py list /Users/jp/Projects/active/codex-tool-dev/docs/tickets --include-closed
```

Expected: both new tickets appear in the output with `status: open`.

---

### Task 5: Final Verification And Diff Review

**Files:**
- All files changed in Tasks 1-4.

- [ ] **Step 1: Run focused Ticket tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
    tests/test_docs_contract.py \
    tests/test_hook.py \
    tests/test_envelope.py \
    tests/test_ingest.py \
    tests/test_capture.py \
    tests/test_update_refinement.py \
    tests/test_doctor.py \
    -q
```

Expected: focused tests pass.

- [ ] **Step 2: Run full Ticket tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: full Ticket suite passes, or pre-existing baseline failures are clearly separated from this slice.

- [ ] **Step 3: Run Handoff bridge checks if Handoff changed**

Run only if files under `plugins/turbo-mode/handoff/` changed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_defer.py tests/test_cli_commands.py tests/test_skill_docs.py -q
```

Expected: Handoff bridge tests pass if Handoff files changed.

- [ ] **Step 4: Run changed-path lint**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
    plugins/turbo-mode/ticket/scripts/ticket_payloads.py \
    plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
    plugins/turbo-mode/ticket/scripts/ticket_envelope.py \
    plugins/turbo-mode/ticket/scripts/ticket_capture.py \
    plugins/turbo-mode/ticket/scripts/ticket_update.py \
    plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
    plugins/turbo-mode/ticket/scripts/ticket_triage.py \
    plugins/turbo-mode/ticket/tests/test_docs_contract.py \
    plugins/turbo-mode/ticket/tests/test_hook.py \
    plugins/turbo-mode/ticket/tests/test_envelope.py \
    plugins/turbo-mode/ticket/tests/test_ingest.py \
    plugins/turbo-mode/ticket/tests/test_capture.py \
    plugins/turbo-mode/ticket/tests/test_update_refinement.py \
    plugins/turbo-mode/ticket/tests/test_doctor.py
```

Expected: lint passes.

- [ ] **Step 5: Run whitespace gate**

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 6: Review final diff for forbidden readiness scope**

```bash
git diff -- plugins/turbo-mode/ticket/scripts/ticket_engine_core.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_envelope.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_capture.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_update.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_doctor.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_triage.py
git diff -- plugins/turbo-mode/ticket/scripts/ticket_payloads.py
git diff -- docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md
```

Run the source-only forbidden runtime-readiness scope gate:

```bash
rg -n '\.codex/ticket-runtime-proof\.json|ticket-runtime-proof|app-server inventory|app_server|live hook smoke|live hook-mediated smoke' \
  plugins/turbo-mode/ticket/scripts \
  plugins/turbo-mode/ticket/hooks
```

Expected:

- `ticket_engine_core.py` has no new runtime-readiness gate.
- `ticket_envelope.py`, `ticket_capture.py`, and `ticket_update.py` contain no runtime-readiness work.
- No source file writes `.codex/ticket-runtime-proof.json`.
- No source file adds app-server inventory capture.
- No source file adds live hook smoke.
- The source-only `rg` gate returns no matches.
- `ticket_engine_runner.py` performs processed replay detection before ticket creation.
- `ticket_payloads.py` only deletes files under `<PROJECT_ROOT>/.codex/ticket-tmp/`.
- The activation readiness ticket carries all runtime-readiness follow-up scope.

- [ ] **Step 7: Check git status**

```bash
git status --short --branch
```

Expected: changed files are exactly the planned files, plus generated test caches only if the verification commands created them. Remove generated residue with `trash` when cleanup is in scope.

## Implementation Notes

- This plan is intentionally source-local. It does not certify installed runtime behavior.
- Source edits here do not prove the installed Codex plugin cache has been refreshed.
- Current `agent + auto_audit + execute` behavior remains the existing guarded provenance/trust model until the activation-capable runtime readiness ticket lands.
- Processed envelopes stay indefinitely in `.processed/`; do not add pruning in this slice.
- The processed-envelope filename is the v1.0 idempotency key. Different filenames are different ids even if content is similar.

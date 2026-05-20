# Ticket Human Transcript Recovery Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ticket's user-facing capture, update, ingest, and recovery paths explain recoverable failures in transcript-safe language without exposing payload mechanics, canonical command repair, or hook provenance internals.

**Architecture:** Treat the human transcript as the product boundary. Add a tiny shared recovery-hint taxonomy in `scripts/ticket_ux.py`, attach `data.recovery_hint` at user-facing mutation and recovery surfaces, keep backend `message` strings safe enough to quote for the selected common failures, and update Ticket plus Handoff defer skills so they render a deterministic safe projection instead of pasting raw JSON envelopes. Keep low-level direct engine/debug surfaces technical unless their `message`/`recovery_hint` response fields bubble into `ticket_capture.py`, `ticket_update.py`, `ticket_engine_user.py ingest`, `ticket_engine_agent.py ingest`, `ticket_doctor.py diagnose`, or Handoff `defer` reporting.

**Tech Stack:** Python >=3.11, pytest, JSON response envelopes, Markdown skill docs, bytecode-safe `uv run` verification.

---

## Decision Freeze

These decisions are frozen for this implementation. If live source makes one impossible, stop and report the conflict before widening scope.

| Area | Frozen decision |
| --- | --- |
| Product boundary | The human transcript is the first-class interface. |
| Ingest stdout | `ticket_engine_user.py ingest` and `ticket_engine_agent.py ingest` stdout stays a machine-readable JSON envelope; the human transcript is an allowlisted projection rendered by skills. |
| Ingest projection | Skills may render only `data.recovery_hint.summary`, `data.recovery_hint.next_step`, safe `message`, top-level `ticket_id`, duplicate candidate ticket IDs, and user-safe ingest outcome prose. Raw `data` fields are not transcript fields. |
| Hidden mechanics | Payload files, canonical command shape, and hook provenance remain implementation details. |
| Structured hint | User-facing recoverable failures expose `data.recovery_hint`. |
| Hint safety | Whenever `data.recovery_hint` appears on a user-facing surface, the full object, including `code`, is safe to show directly to a human user. |
| Hint schema | `{"code": str, "summary": str, "next_step": str}` only. Do not add `audience` in this slice. |
| Hint codes | Only `stale_plan`, `trust_setup`, `retry_preview`, `cleanup_stale_preview`, `policy_blocked`, and `preflight_failed`. |
| Trust/setup | Trust/setup failures stop the flow. They do not recommend bypassing the guard, changing command shape, or retrying blindly. |
| Trust/setup wording | `plugin hook setup` is allowed setup-level recovery language only in the `trust_setup` next step; hook/provenance field names, verified provenance detail, and command-shape repair remain hidden. |
| Temp state split | Use `retry_preview` for unusable current preview state. Use `cleanup_stale_preview` only for old abandoned temp state reported by doctor. |
| Ingest `need_fields` split | Missing or malformed ingest request payload shape uses `retry_preview`; invalid `DeferredWorkEnvelope` content after envelope read uses `preflight_failed`. |
| Policy vs preflight | Keep `policy_blocked` and `preflight_failed` distinct. |
| Low-level debug | Direct `classify`, `plan`, `preflight`, `execute`, and compatibility/debug paths may remain technical unless their output is surfaced by a user-facing wrapper. |
| Runtime scope | Do not mutate installed cache, app-server runtime state, or personal plugin copies in this source-local slice. |

## Non-Goals

- Do not redesign the capture/update preview payload model.
- Do not add a new command router or skill.
- Do not make `ticket_workflow.py` user-facing.
- Do not broaden the engine response contract beyond the selected recovery-hint field.
- Do not scrub every low-level debug message.
- Do not claim raw ingest stdout JSON can be pasted into a human transcript.
- Do not add locking, queueing, runtime readiness, live hook smoke, or installed-cache proof.
- Do not change Ticket's trust model, hook allowlist, or execute provenance requirements.
- Do not change ticket schema, IDs, or DeferredWorkEnvelope format.

## Source Files To Read First

Before implementation, re-read these live files. This plan is not a substitute for source truth.

- `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- `plugins/turbo-mode/ticket/scripts/ticket_paths.py`
- `plugins/turbo-mode/ticket/scripts/ticket_payloads.py`
- `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`
- `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md`
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- `plugins/turbo-mode/handoff/skills/defer/SKILL.md`
- `plugins/turbo-mode/handoff/references/skill-details.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/tests/test_ux.py`
- `plugins/turbo-mode/ticket/tests/test_capture.py`
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- `plugins/turbo-mode/ticket/tests/test_ingest.py`
- `plugins/turbo-mode/ticket/tests/test_doctor.py`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- `plugins/turbo-mode/handoff/tests/test_skill_docs.py`
- Available `writing-principles` skill before Task 5 skill/reference edits. Prefer repo-local `.codex/skills/writing-principles/SKILL.md`; if absent, use `/Users/jp/.agents/skills/writing-principles/SKILL.md`. If no applicable copy is available, stop before editing `SKILL.md` or instruction-style Markdown.

## File Structure

- `docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md` - this plan.
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py` - canonical recovery-hint taxonomy and safe attachment helpers.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - attach hints to capture prepare/execute recoverable failures.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - attach hints to update prepare/execute recoverable failures.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - attach hints for ingest and runner-level trust/setup or payload boundary failures.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` - read-only reference for low-level engine messages that may remain technical in this slice.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - attach `cleanup_stale_preview` to the top-level diagnose response envelope when stale temp payloads are reported.
- `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md` - tell the skill to render `recovery_hint` first and translate failures into user recovery.
- `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md` - same, with ticket-specific context.
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` - same, for stale cleanup reporting and confirmed cleanup.
- `plugins/turbo-mode/handoff/skills/defer/SKILL.md` - keep Ticket ingest payloads and envelope paths out of the human transcript while still using them as internal execution steps.
- `plugins/turbo-mode/handoff/references/skill-details.md` - mirror the Handoff defer transcript boundary for Ticket ingest.
- `plugins/turbo-mode/ticket/HANDBOOK.md` - operator-facing contract for `recovery_hint` without hiding lower-level debug docs.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - response contract for transcript-safe hints on user-facing surfaces.
- `plugins/turbo-mode/ticket/tests/test_ux.py` - taxonomy schema, exact wording, exact forbidden transcript vocabulary, and internal-leak tests.
- `plugins/turbo-mode/ticket/tests/test_capture.py` - capture stale/retry/trust/policy hint coverage.
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py` - update stale/retry/trust/preflight hint coverage.
- `plugins/turbo-mode/ticket/tests/test_ingest.py` - ingest trust/setup, pre-dispatch context, policy/preflight, duplicate candidate, normal success, and partial-success transcript-safety coverage.
- `plugins/turbo-mode/ticket/tests/test_doctor.py` - stale cleanup hint coverage.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` - static docs/skill contract checks.
- `plugins/turbo-mode/handoff/tests/test_skill_docs.py` - Handoff defer skill/reference transcript-boundary checks.

## Recovery Hint Contract

Add the taxonomy in `plugins/turbo-mode/ticket/scripts/ticket_ux.py`.

```python
RECOVERY_HINTS: dict[str, dict[str, str]] = {
    "stale_plan": {
        "summary": "The saved preview is no longer current.",
        "next_step": "Rerun the preview, review the updated result, then confirm again.",
    },
    "trust_setup": {
        "summary": "Ticket setup needs attention before this write can continue.",
        "next_step": (
            "Stop without writing. Run ticket-doctor diagnostics or verify the plugin "
            "hook setup before retrying."
        ),
    },
    "retry_preview": {
        "summary": "The saved preview state is no longer usable.",
        "next_step": "Rerun the preview and confirm again before writing.",
    },
    "cleanup_stale_preview": {
        "summary": "Old abandoned Ticket preview state can be cleaned up after review.",
        "next_step": "Use ticket-doctor stale cleanup after reviewing the reported items.",
    },
    "policy_blocked": {
        "summary": "This write is blocked by Ticket policy.",
        "next_step": "Keep the ticket unchanged and adjust the request or policy before retrying.",
    },
    "preflight_failed": {
        "summary": "Ticket checks did not pass.",
        "next_step": "Review the preview or check details, update the request, then rerun preview.",
    },
}

def recovery_hint(code: str) -> dict[str, str]:
    """Return a transcript-safe recovery hint for a known recovery code."""
    try:
        hint = RECOVERY_HINTS[code]
    except KeyError as exc:
        raise ValueError(f"unknown recovery hint code: {code!r}") from exc
    return {"code": code, **hint}


INTERNAL_RECOVERY_TERMS = (
    "hook_injected",
    "hook_request_origin",
    "request_origin",
    "origin_mismatch",
    "verified hook provenance",
    "payload",
    "payload path",
    "payload_file",
    "envelope_path",
    "processed_path",
    "incoming_envelope_path",
    "ticket_path",
    "envelope_move_error",
    "PAYLOAD_PATH",
    "canonical command",
    "python3 -B",
)

INTERNAL_RECOVERY_PATH_PATTERNS = (
    r"(?<![A-Za-z0-9_.-])/(?:Users|home|workspace|workspaces|private|tmp|var)/",
    r"[A-Za-z]:\\",
)


def attach_recovery_hint(response: dict[str, Any], code: str) -> dict[str, Any]:
    """Return response with a transcript-safe recovery hint in data."""
    updated = dict(response)
    data = dict(updated.get("data") or {})
    data["recovery_hint"] = recovery_hint(code)
    updated["data"] = data
    return updated


def attach_engine_recovery_hint(response: Any, code: str) -> Any:
    """Attach a transcript-safe recovery hint to an EngineResponse-like object."""
    data = dict(getattr(response, "data", {}) or {})
    data["recovery_hint"] = recovery_hint(code)
    response.data = data
    return response


def recovery_hint_code_for_response(response: dict[str, Any]) -> str | None:
    """Choose the default user-facing recovery code for a response dict."""
    data = response.get("data")
    if isinstance(data, dict) and "recovery_hint" in data:
        return None
    if response.get("error_code") == "stale_plan":
        return "stale_plan"
    if response.get("error_code") == "parse_error":
        return "retry_preview"
    if response.get("error_code") == "origin_mismatch":
        return "trust_setup"
    if response.get("state") == "policy_blocked":
        return "policy_blocked"
    if response.get("state") == "preflight_failed":
        return "preflight_failed"
    return None
```

The exact helper names may change during implementation if the surrounding code demands it, but the schema, codes, and user-safe text above are the contract. The `code` field is not exempt from transcript safety; code names must avoid hidden implementation mechanics. `recovery_hint_code_for_response()` is only a classifier. Callers must sanitize the paired `message` for the selected code before attaching the hint, especially for `parse_error` and `origin_mismatch` responses whose original messages may quote path, payload, or provenance-shaped details.

## Stop Conditions

- If implementation needs to expose `hook_injected`, `hook_request_origin`, `request_origin`, `origin_mismatch`, `PAYLOAD_PATH`, `payload`, `payload path`, `payload_file`, `envelope_path`, `processed_path`, `incoming_envelope_path`, `ticket_path`, `envelope_move_error`, canonical command repair, raw absolute temp/workspace paths, or `python3 -B` in a user-facing `message`, `recovery_hint`, or transcript projection, stop and redesign that path.
- If a recovery hint code would contain hidden implementation mechanics such as `payload`, `envelope`, hook/provenance field names, command shape, or raw path vocabulary, stop and rename the code before it becomes a durable contract.
- If transcript-facing runtime output or skill recovery prose uses `plugin hook setup` anywhere except the `trust_setup` next step or skill explanation of that next step, stop and remove it. Control-doc and operator-contract mentions may use the phrase only to document that boundary.
- If a user-facing response carries `data.recovery_hint`, the paired `message` must also avoid payload path mechanics, envelope path mechanics, canonical command repair, raw temp/workspace paths, and hook/provenance field names.
- If a response would get `data.recovery_hint` only by running `recovery_hint_code_for_response()` while preserving an unsafe `message`, stop. Sanitize the paired `message` first, then attach the hint.
- If an ingest response gets `data.recovery_hint`, sanitize the paired `message` before attaching or printing the hint. Do not attach a hint to an ingest response whose message still quotes `envelope_path`, containment boundaries, or raw paths.
- If Handoff `defer` or a Ticket skill would paste full ingest stdout into the human transcript, stop. Parse the JSON envelope and render only the allowlisted transcript projection.
- If implementation decides full ingest stdout itself must be transcript-safe, remove or split the path-bearing `data` fields instead of relying on skill instructions.
- If a trust/setup failure suggests bypassing the guard, changing command shape, or forcing execute, stop.
- If the implementation changes `error_code="origin_mismatch"` to another machine code only to make a user-safe trust/setup message easier, stop. Preserve the machine code and attach `trust_setup`.
- If adding `recovery_hint` requires changing all engine stages at once, stop and narrow to the user-facing surfaces.
- If a test would need installed runtime, app-server inventory, personal plugin sync, or live hook smoke, stop. This plan is source-local.
- If a direct debug path remains technical but is not reached through capture/update/ingest/doctor, do not widen scope just to scrub it.
- If stale cleanup would delete files as part of this UX work, stop unless the user explicitly asks to run cleanup. Tests may use temp fixtures only.

## Commit Boundaries

- Commit 1: plan only.
- Commit 2: shared taxonomy and unit tests.
- Commit 3: capture/update/ingest response hints and focused behavior tests.
- Commit 4: Ticket and Handoff skill/docs wording plus docs contract tests.
- Commit 5: doctor stale cleanup hint tests and final verification, if not already covered by Commit 3 or 4.

These boundaries are authoritative for implementation. Do not replace them with one all-files source commit unless the user explicitly asks for a squash or single-commit closeout.

---

### Task 0: Baseline And Branch Gate

**Files:**
- Read: `docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch is `fix/ticket-human-transcript-ux` and unrelated dirty work is preserved.

- [ ] **Step 2: Require the intended implementation branch**

```bash
git branch --show-current
```

Expected: output is exactly `fix/ticket-human-transcript-ux`.

If the output is `main`, run:

```bash
git switch -c fix/ticket-human-transcript-ux
```

Expected: branch switches to `fix/ticket-human-transcript-ux`.

If the output is any other branch name or empty because `HEAD` is detached, stop and decide explicitly whether to switch to `fix/ticket-human-transcript-ux` or revise the branch target. Do not continue silently on a wrong non-`main` branch.

- [ ] **Step 3: Run current focused baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_ux.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_doctor.py \
  tests/test_docs_contract.py \
  -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_skill_docs.py -q
```

Expected: all selected Ticket tests and Handoff skill docs tests pass before changes, or failures are recorded before implementation.

### Task 1: Add Recovery Hint Taxonomy

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Test: `plugins/turbo-mode/ticket/tests/test_ux.py`

- [ ] **Step 1: Add failing taxonomy tests**

Append tests like these to `plugins/turbo-mode/ticket/tests/test_ux.py`:

```python
import re

from scripts.ticket_ux import (
    INTERNAL_RECOVERY_TERMS,
    INTERNAL_RECOVERY_PATH_PATTERNS,
    RECOVERY_HINTS,
    attach_recovery_hint,
    recovery_hint,
)
```

If imports already exist, add `import re` near the other stdlib imports and update the existing `from scripts.ticket_ux import ...` block instead of adding a second import later in the file.

Then add:

```python
def test_recovery_hint_contract_is_transcript_safe() -> None:
    expected_codes = {
        "stale_plan",
        "trust_setup",
        "retry_preview",
        "cleanup_stale_preview",
        "policy_blocked",
        "preflight_failed",
    }

    assert set(RECOVERY_HINTS) == expected_codes
    assert recovery_hint("trust_setup") == {
        "code": "trust_setup",
        "summary": "Ticket setup needs attention before this write can continue.",
        "next_step": (
            "Stop without writing. Run ticket-doctor diagnostics or verify the plugin "
            "hook setup before retrying."
        ),
    }
    for code in expected_codes:
        hint = recovery_hint(code)
        assert set(hint) == {"code", "summary", "next_step"}
        rendered = " ".join(hint.values())
        for term in INTERNAL_RECOVERY_TERMS:
            assert term.lower() not in rendered.lower()
        for pattern in INTERNAL_RECOVERY_PATH_PATTERNS:
            assert re.search(pattern, rendered) is None


def test_attach_recovery_hint_preserves_response_data() -> None:
    response = {
        "state": "preflight_failed",
        "message": "Ticket checks did not pass.",
        "error_code": "preflight_failed",
        "data": {"checks_failed": ["missing_acceptance_criteria"]},
    }

    updated = attach_recovery_hint(response, "preflight_failed")

    assert updated["data"]["checks_failed"] == ["missing_acceptance_criteria"]
    assert updated["data"]["recovery_hint"] == {
        "code": "preflight_failed",
        "summary": "Ticket checks did not pass.",
        "next_step": "Review the preview or check details, update the request, then rerun preview.",
    }
    assert "recovery_hint" not in response["data"]


def test_transcript_safety_terms_match_expected_internal_leak_vocabulary() -> None:
    expected_terms = (
        "hook_injected",
        "hook_request_origin",
        "request_origin",
        "origin_mismatch",
        "verified hook provenance",
        "payload",
        "payload path",
        "payload_file",
        "envelope_path",
        "processed_path",
        "incoming_envelope_path",
        "ticket_path",
        "envelope_move_error",
        "PAYLOAD_PATH",
        "canonical command",
        "python3 -B",
    )

    assert tuple(INTERNAL_RECOVERY_TERMS) == expected_terms


def test_transcript_safety_path_patterns_cover_known_host_shapes() -> None:
    examples = (
        "/Users/example/project/.codex/ticket-tmp/payload.json",
        "/home/runner/work/project/payload.json",
        "/workspace/project/docs/tickets/.envelopes/item.json",
        "/workspaces/project/docs/tickets/.envelopes/item.json",
        "/private/tmp/project/tickets/.envelopes/item.json",
        "/tmp/project/payload.json",
        "/var/folders/example/payload.json",
        r"C:\Users\example\project\payload.json",
    )

    for rendered in examples:
        assert any(re.search(pattern, rendered) for pattern in INTERNAL_RECOVERY_PATH_PATTERNS), rendered
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ux.py -q
```

Expected: fails because `recovery_hint`, `attach_recovery_hint`, `INTERNAL_RECOVERY_TERMS`, and `INTERNAL_RECOVERY_PATH_PATTERNS` do not exist yet.

- [ ] **Step 3: Implement taxonomy and helpers**

Add the helper code from the "Recovery Hint Contract" section to `plugins/turbo-mode/ticket/scripts/ticket_ux.py`. Keep imports to stdlib only; `Any` is already imported in the file.

- [ ] **Step 4: Run tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ux.py -q
```

Expected: `tests/test_ux.py` passes.

### Task 2: Attach Hints To Capture And Update

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Test: `plugins/turbo-mode/ticket/tests/test_capture.py`
- Test: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`

- [ ] **Step 1: Add capture tests for retry, stale, trust, and policy hints**

Add focused assertions to existing tests rather than duplicating fixture setup:

```python
def _assert_hint(response: dict, code: str) -> None:
    hint = response["data"]["recovery_hint"]
    assert hint["code"] == code
    assert set(hint) == {"code", "summary", "next_step"}
    rendered = " ".join(hint.values()) + " " + response["message"]
    for term in INTERNAL_RECOVERY_TERMS:
        assert term.lower() not in rendered.lower()
    for pattern in INTERNAL_RECOVERY_PATH_PATTERNS:
        assert re.search(pattern, rendered) is None
```

Import `re`, `INTERNAL_RECOVERY_TERMS`, and `INTERNAL_RECOVERY_PATH_PATTERNS` at the top of the test file.

Add assertions:

```python
assert execute["error_code"] == "stale_plan"
_assert_hint(execute, "stale_plan")
```

For `test_execute_without_prepare_returns_stale_plan`-style capture coverage, assert `retry_preview` when the prepare artifact is missing or malformed:

```python
response = run_capture("execute", payload_path)

assert response["state"] == "preflight_failed"
assert response["error_code"] == "stale_plan"
_assert_hint(response, "retry_preview")
```

For trust/setup, remove trust fields from a prepared payload before execute:

```python
payload = json.loads(payload_path.read_text(encoding="utf-8"))
payload.pop("hook_injected", None)
payload.pop("hook_request_origin", None)
_write_payload(payload_path, payload)

response = run_capture("execute", payload_path)

assert response["state"] == "policy_blocked"
_assert_hint(response, "trust_setup")
assert response["message"] == "Ticket setup needs attention before this write can continue."
```

Add capture helper coverage for malformed provenance-shaped origin responses. Do not try to reach this through a wrapper execute path: `hook_request_origin` is part of the execute fingerprint, so mutating it after prepare should produce `stale_plan` before core preflight. Instead, test the local sanitizer/helper directly:

```python
def test_default_hint_sanitizes_origin_mismatch_message_before_attaching_hint() -> None:
    response = ticket_capture._with_default_recovery_hint(
        {
            "state": "escalate",
            "message": "Cannot determine caller identity: request_origin='/Users/example/project'",
            "error_code": "origin_mismatch",
        }
    )

    assert response["state"] == "escalate"
    assert response["error_code"] == "origin_mismatch"
    _assert_hint(response, "trust_setup")
    assert response["message"] == "Ticket setup needs attention before this write can continue."
```

Use the existing `import scripts.ticket_capture as ticket_capture`; add it near the other imports if the file no longer has it.

- [ ] **Step 2: Add update tests for retry, stale, trust, and preflight hints**

Use the existing update stale-plan tests and add `_assert_hint(response, "stale_plan")`.

For execute without prepare:

```python
response = run_update("execute", payload_path)

assert response["state"] == "preflight_failed"
assert response["error_code"] == "stale_plan"
_assert_hint(response, "retry_preview")
```

For trust/setup, prepare first, remove `hook_injected` and `hook_request_origin`, then execute and assert `trust_setup`.

Add update helper coverage for the same malformed provenance-shaped origin response. Keep this as a helper test for the same reachability reason: wrapper execute fingerprint checks should stop mutated trust-origin payloads before dispatch.

```python
def test_default_hint_sanitizes_origin_mismatch_message_before_attaching_hint() -> None:
    response = ticket_update._with_default_recovery_hint(
        {
            "state": "escalate",
            "message": "Cannot determine caller identity: request_origin='/Users/example/project'",
            "error_code": "origin_mismatch",
        }
    )

    assert response["state"] == "escalate"
    assert response["error_code"] == "origin_mismatch"
    _assert_hint(response, "trust_setup")
    assert response["message"] == "Ticket setup needs attention before this write can continue."
```

Add `import scripts.ticket_update as ticket_update` near the other imports if it does not already exist.

For preflight, use an existing close-readiness/precondition failure path and assert either `preflight_failed` if the response state is `preflight_failed`, or do not force a hint if the state is `invalid_transition`. Do not reclassify `invalid_transition` as `preflight_failed`.

- [ ] **Step 3: Run capture/update tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  -q
```

Expected: new hint assertions fail.

- [ ] **Step 4: Import helpers and attach hints**

In both `ticket_capture.py` and `ticket_update.py`, import:

```python
from scripts.ticket_ux import attach_recovery_hint, recovery_hint_code_for_response
```

Add a local wrapper near `_engine_response_to_dict`:

```python
_SAFE_MESSAGE_BY_RECOVERY_CODE = {
    "stale_plan": "The saved preview is no longer current.",
    "trust_setup": "Ticket setup needs attention before this write can continue.",
    "retry_preview": "The saved preview state is no longer usable.",
    "policy_blocked": "This write is blocked by Ticket policy.",
    "preflight_failed": "Ticket checks did not pass.",
}


def _with_default_recovery_hint(response: dict[str, Any]) -> dict[str, Any]:
    code = recovery_hint_code_for_response(response)
    if code is None:
        return response
    safe_response = dict(response)
    safe_response["message"] = _SAFE_MESSAGE_BY_RECOVERY_CODE.get(
        code,
        safe_response.get("message", ""),
    )
    return attach_recovery_hint(safe_response, code)
```

Use it on responses returned from `_load_*_context()` and `dispatch_stage()` when those responses leave the user-facing wrapper. Do not call `attach_recovery_hint()` directly on a response whose current `message` has not been sanitized for that recovery code.

For payload read/shape/path failures from `_load_*_context()`, return a user-safe message and attach `retry_preview`:

```python
return attach_recovery_hint(
    _response(
        "escalate",
        "The saved preview state is no longer usable.",
        error_code="parse_error",
    ),
    "retry_preview",
)
```

If the underlying state is `policy_blocked` because the wrapper cannot resolve the project or tickets boundary, keep the state and error code, but use the `policy_blocked` hint and a user-safe policy message. Do not quote the rejected path in user-facing wrapper output.

For any capture/update response that carries `data.recovery_hint`, add or update tests so `_assert_hint()` covers the entire paired `message` plus hint. A response with a hint must not include `payload`, `Payload path`, `payload_file`, raw absolute temp/workspace paths, canonical command text, hook/provenance field names, `request_origin`, or `origin_mismatch`.

For missing or malformed prepare artifacts in execute, attach `retry_preview` explicitly:

```python
return attach_recovery_hint(
    _response(
        "preflight_failed",
        "The saved preview state is no longer usable.",
        error_code="stale_plan",
    ),
    "retry_preview",
)
```

For fingerprint mismatches, keep `error_code="stale_plan"` and attach `stale_plan`:

```python
return attach_recovery_hint(
    _response(
        "preflight_failed",
        "The saved preview is no longer current.",
        error_code="stale_plan",
    ),
    "stale_plan",
)
```

- [ ] **Step 5: Sanitize runner execute trust/setup failures before capture/update pass gate**

Capture/update execute use `load_runner_context(None, "execute", payload_path)` before their wrapper fingerprint checks. Missing trust fields therefore surface from `ticket_engine_runner.py`, not from `recovery_hint_code_for_response()` in the wrappers. Patch the shared runner before expecting capture/update trust tests to pass.

In `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`, import:

```python
from scripts.ticket_ux import attach_engine_recovery_hint
```

For execute trust errors in `load_runner_context()`, keep `state="policy_blocked"` and `error_code="policy_blocked"`, but replace the message and attach `trust_setup`:

```python
if trust_errors:
    response = EngineResponse(
        state="policy_blocked",
        message="Ticket setup needs attention before this write can continue.",
        error_code="policy_blocked",
    )
    if subcommand == "execute":
        return None, attach_engine_recovery_hint(response, "trust_setup")
    return None, response
```

Do not attach `trust_setup` to ingest here yet. Task 3 adds ingest trust/setup assertions and extends this same branch for `subcommand == "ingest"` after the ingest tests are written.

- [ ] **Step 6: Run capture/update tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  -q
```

Expected: tests pass.

### Task 3: Attach Hints To Ingest And Remaining Runner Setup

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Test: `plugins/turbo-mode/ticket/tests/test_ingest.py`

- [ ] **Step 1: Add ingest trust/setup, context, success, parse/read, and policy hint tests**

In `plugins/turbo-mode/ticket/tests/test_ingest.py`, add helpers that parse the JSON emitted by `run()` using `capsys` and assert the deterministic transcript projection is safe. The raw stdout JSON envelope is machine-readable; this test intentionally validates the fields skills are allowed to render, not every machine/debug key in `data`.

```python
import re

from scripts.ticket_ux import INTERNAL_RECOVERY_PATH_PATTERNS, INTERNAL_RECOVERY_TERMS


def _run_and_read_response(
    capsys: pytest.CaptureFixture[str],
    request_origin: str,
    argv: list[str],
) -> tuple[int, dict]:
    exit_code = run(request_origin, argv=argv, prog="test")
    captured = capsys.readouterr()
    assert captured.err == ""
    response = json.loads(captured.out)
    assert isinstance(response, dict)
    return exit_code, response


_INGEST_TRANSCRIPT_OUTCOME_MESSAGES = {
    "created": "Ticket was created.",
    "duplicate_replay": "That Ticket ingest request was already processed; no ticket was created.",
    "created_envelope_move_failed": "Ticket was created, but Ticket could not finish ingest cleanup.",
}


def _ingest_transcript_projection(response: dict) -> dict[str, object]:
    data = response.get("data") or {}
    hint = data.get("recovery_hint") if isinstance(data, dict) else None
    projection: dict[str, object] = {
        "message": response.get("message"),
    }
    if hint is not None:
        projection["recovery_hint"] = hint
    ticket_id = response.get("ticket_id")
    if isinstance(ticket_id, str) and ticket_id:
        projection["ticket_id"] = ticket_id
    if isinstance(data, dict):
        duplicate_of = data.get("duplicate_of")
        if isinstance(duplicate_of, str) and duplicate_of:
            projection["duplicate_candidate_ticket_id"] = duplicate_of
        outcome = data.get("ingest_outcome")
        if isinstance(outcome, str) and outcome in _INGEST_TRANSCRIPT_OUTCOME_MESSAGES:
            projection["ingest_outcome"] = _INGEST_TRANSCRIPT_OUTCOME_MESSAGES[outcome]
    return projection


def _assert_ingest_transcript_projection_safe(response: dict) -> None:
    rendered = json.dumps(_ingest_transcript_projection(response), sort_keys=True)
    for term in INTERNAL_RECOVERY_TERMS:
        assert term.lower() not in rendered.lower()
    for pattern in INTERNAL_RECOVERY_PATH_PATTERNS:
        assert re.search(pattern, rendered) is None
```

Add a missing-trust test:

```python
def test_ingest_missing_trust_fields_returns_safe_setup_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    envelopes_dir = tickets_dir / ".envelopes"
    envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps({"envelope_path": str(envelope_path), "tickets_dir": str(tickets_dir)}))

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["data"]["recovery_hint"]["code"] == "trust_setup"
    assert response["message"] == "Ticket setup needs attention before this write can continue."
    _assert_ingest_transcript_projection_safe(response)
```

Add an origin-mismatch test that preserves the machine code:

```python
def test_ingest_origin_mismatch_preserves_error_code_with_setup_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    envelopes_dir = tickets_dir / ".envelopes"
    envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "envelope_path": str(envelope_path),
                "tickets_dir": str(tickets_dir),
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "agent",
            }
        )
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 1
    assert response["state"] == "escalate"
    assert response["error_code"] == "origin_mismatch"
    assert response["data"]["recovery_hint"]["code"] == "trust_setup"
    assert response["message"] == "Ticket setup needs attention before this write can continue."
    _assert_ingest_transcript_projection_safe(response)
```

Add a parse/read test for missing ingest payload files:

```python
def test_ingest_missing_payload_file_returns_safe_retry_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    payload_file = tmp_path / "missing-payload.json"

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 1
    assert response["state"] == "escalate"
    assert response["error_code"] == "parse_error"
    assert response["data"]["recovery_hint"]["code"] == "retry_preview"
    assert response["message"] == "The saved preview state is no longer usable."
    _assert_ingest_transcript_projection_safe(response)
```

Add pre-dispatch context-error tests for `load_runner_context()` failures that occur before `_dispatch_ingest()` can sanitize anything:

```python
@pytest.mark.parametrize("tickets_dir_value", [123, "../outside-tickets"])
def test_ingest_tickets_dir_context_errors_return_safe_policy_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tickets_dir_value: object,
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    envelopes_dir = tickets_dir / ".envelopes"
    envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "envelope_path": str(envelope_path),
                "tickets_dir": tickets_dir_value,
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
            }
        ),
        encoding="utf-8",
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "policy_blocked"
    assert response["data"]["recovery_hint"]["code"] == "policy_blocked"
    assert response["message"] == "Ticket ingest is blocked by Ticket policy."
    _assert_ingest_transcript_projection_safe(response)


def test_ingest_missing_project_root_returns_safe_policy_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    envelopes_dir = tickets_dir / ".envelopes"
    envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "envelope_path": str(envelope_path),
                "tickets_dir": str(tickets_dir),
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
            }
        ),
        encoding="utf-8",
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "policy_blocked"
    assert response["data"]["recovery_hint"]["code"] == "policy_blocked"
    assert response["message"] == "Ticket ingest is blocked by Ticket policy."
    _assert_ingest_transcript_projection_safe(response)
```

Add a malformed ingest request test for missing `envelope_path`:

```python
def test_ingest_missing_envelope_path_returns_safe_retry_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "tickets_dir": str(tickets_dir),
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
            }
        )
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 2
    assert response["state"] == "need_fields"
    assert response["error_code"] == "need_fields"
    assert response["data"]["recovery_hint"]["code"] == "retry_preview"
    assert response["message"] == "The saved preview state is no longer usable."
    _assert_ingest_transcript_projection_safe(response)
```

Add or update the invalid envelope-content test so it does not use the same recovery copy as runner payload-shape failures:

```python
def test_ingest_invalid_envelope_returns_safe_preflight_hint(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    envelopes_dir = tickets_dir / ".envelopes"
    bad_envelope = {"envelope_version": "1.0"}
    envelope_path = _write_envelope(bad_envelope, envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "envelope_path": str(envelope_path),
                "tickets_dir": str(tickets_dir),
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
            }
        ),
        encoding="utf-8",
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 2
    assert response["state"] == "need_fields"
    assert response["error_code"] == "need_fields"
    assert response["data"]["recovery_hint"]["code"] == "preflight_failed"
    assert response["message"] == "Ticket checks did not pass."
    assert response["data"]["validation_errors"]
    _assert_ingest_transcript_projection_safe(response)
    assert envelope_path.exists()
```

Add or update normal created-ingest success coverage so the happy path cannot leak the ticket path through the allowed projection:

```python
def test_ingest_created_response_has_safe_transcript_projection(
    self,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_project_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    tickets_dir = tmp_path / "tickets"
    envelopes_dir = tickets_dir / ".envelopes"
    envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(
        json.dumps(
            {
                "envelope_path": str(envelope_path),
                "tickets_dir": str(tickets_dir),
                "session_id": "test-session",
                "hook_injected": True,
                "hook_request_origin": "user",
            }
        ),
        encoding="utf-8",
    )

    exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

    assert exit_code == 0
    assert response["state"] == "ok_create"
    assert response["message"] == "Ticket was created."
    assert response["data"]["ingest_outcome"] == "created"
    assert response["data"]["ticket_created"] is True
    assert response["data"]["ticket_path"]
    assert response["data"]["processed_path"]
    assert response["data"]["incoming_envelope_path"] == str(envelope_path)
    assert "recovery_hint" not in response["data"]
    projection = _ingest_transcript_projection(response)
    assert projection["message"] == "Ticket was created."
    assert projection["ingest_outcome"] == "Ticket was created."
    assert "ticket_path" not in projection
    assert "processed_path" not in projection
    assert "incoming_envelope_path" not in projection
    _assert_ingest_transcript_projection_safe(response)
    assert len(list(tickets_dir.glob("*.md"))) == 1
```

For the existing duplicate-candidate ingest test, keep the machine duplicate details but prove the allowlisted projection is safe:

```python
exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(second_payload_file)])

assert exit_code == 1
assert response["state"] == "duplicate_candidate"
assert response["error_code"] == "duplicate_candidate"
assert response.get("data", {}).get("ingest_outcome") != "duplicate_replay"
assert response["data"]["duplicate_of"] == response["ticket_id"]
assert response["data"]["dedup_fingerprint"]
assert response["data"]["target_fingerprint"]
assert response["data"]["action_plan"]["duplicate_candidate"] is True
assert "recovery_hint" not in response["data"]

projection = _ingest_transcript_projection(response)
assert projection["message"].startswith("Potential duplicate")
assert projection["ticket_id"] == response["ticket_id"]
assert projection["duplicate_candidate_ticket_id"] == response["data"]["duplicate_of"]
assert "dedup_fingerprint" not in projection
assert "target_fingerprint" not in projection
assert "action_plan" not in projection
assert "processed_path" not in projection
assert "incoming_envelope_path" not in projection
assert "ticket_path" not in projection
assert "envelope_move_error" not in projection
_assert_ingest_transcript_projection_safe(response)
assert second_envelope.exists()
```

For existing containment and direct-child policy-blocked ingest tests, assert:

```python
assert response["data"]["recovery_hint"]["code"] == "policy_blocked"
assert response["message"] == "Ticket ingest is blocked by Ticket policy."
_assert_ingest_transcript_projection_safe(response)
```

For the existing duplicate/replay test, keep the successful machine outcome but make the message safe:

```python
assert response["state"] == "ok"
assert response["data"]["ingest_outcome"] == "duplicate_replay"
assert "recovery_hint" not in response["data"]
assert response["message"] == "That Ticket ingest request was already processed; no ticket was created."
assert "envelope_path" not in response["message"]
projection = _ingest_transcript_projection(response)
assert projection["ingest_outcome"] == "That Ticket ingest request was already processed; no ticket was created."
assert "processed_path" not in projection
assert "incoming_envelope_path" not in projection
_assert_ingest_transcript_projection_safe(response)
```

For the existing envelope-move partial-success test, keep the machine/debug data but prove the transcript message is safe:

```python
exit_code, response = _run_and_read_response(capsys, "user", ["ingest", str(payload_file)])

assert exit_code == 0
assert response["state"] == "ok_create"
assert response["data"]["ingest_outcome"] == "created_envelope_move_failed"
assert response["data"]["ticket_created"] is True
assert response["data"]["envelope_id"] == envelope_path.name
assert response["data"]["processed_path"] == str(processed_path)
assert response["data"]["incoming_envelope_path"] == str(envelope_path)
assert response["data"]["envelope_move_error"].startswith("simulated move failure")
assert "recovery_hint" not in response["data"]
assert response["message"] == "Ticket was created, but Ticket could not finish ingest cleanup."
projection = _ingest_transcript_projection(response)
assert projection["ingest_outcome"] == "Ticket was created, but Ticket could not finish ingest cleanup."
assert "processed_path" not in projection
assert "incoming_envelope_path" not in projection
_assert_ingest_transcript_projection_safe(response)
assert envelope_path.exists()
assert len(list(tickets_dir.glob("*.md"))) == 1
```

- [ ] **Step 2: Run ingest tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ingest.py -q
```

Expected: new recovery-hint, stdout-envelope, origin-code-preservation, pre-dispatch context-error, duplicate-candidate projection, created-success-message, and transcript-projection safety assertions fail.

- [ ] **Step 3: Attach runner-level hints**

In `ticket_engine_runner.py`, extend the Task 2 import:

```python
from scripts.ticket_ux import attach_engine_recovery_hint, recovery_hint_code_for_response
```

For origin mismatch in `load_runner_context()`, preserve `state="escalate"` and `error_code="origin_mismatch"`, but replace the message and attach `trust_setup`:

```python
return None, attach_engine_recovery_hint(
    EngineResponse(
        state="escalate",
        message="Ticket setup needs attention before this write can continue.",
        error_code="origin_mismatch",
    ),
    "trust_setup",
)
```

For ingest trust errors in `load_runner_context()`, extend the Task 2 execute branch so both `execute` and `ingest` attach `trust_setup`. Keep `state="policy_blocked"` and `error_code="policy_blocked"`, but replace the message:

```python
if trust_errors:
    return None, attach_engine_recovery_hint(
        EngineResponse(
            state="policy_blocked",
            message="Ticket setup needs attention before this write can continue.",
            error_code="policy_blocked",
        ),
        "trust_setup",
)
```

Add one sanitizer helper before `run()` print sites. It must handle both pre-dispatch `load_runner_context()` errors and post-dispatch `_dispatch_ingest()` responses:

```python
def _ingest_need_fields_recovery_code(resp: EngineResponse) -> str:
    data = resp.data if isinstance(resp.data, dict) else {}
    validation_errors = data.get("validation_errors")
    if isinstance(validation_errors, list) and validation_errors:
        return "preflight_failed"
    return "retry_preview"


def _sanitize_user_facing_ingest_response(resp: EngineResponse) -> EngineResponse:
    hint_code = (
        _ingest_need_fields_recovery_code(resp)
        if resp.error_code == "need_fields"
        else recovery_hint_code_for_response(resp.to_dict())
    )
    if hint_code is None:
        return resp
    if hint_code == "trust_setup":
        resp.message = "Ticket setup needs attention before this write can continue."
    elif hint_code == "policy_blocked":
        resp.message = "Ticket ingest is blocked by Ticket policy."
    elif hint_code == "preflight_failed":
        resp.message = "Ticket checks did not pass."
    elif hint_code == "stale_plan":
        resp.message = "The saved preview is no longer current."
    elif hint_code == "retry_preview":
        resp.message = "The saved preview state is no longer usable."
    return attach_engine_recovery_hint(resp, hint_code)
```

In `run()`, remove the stderr-only `{"error": ...}` bypass for ingest parse/read errors. Keep the bypass for non-ingest debug stages if needed, but every `subcommand == "ingest"` error from `load_runner_context()` must be sanitized and printed as a normal stdout response envelope:

```python
context, error = load_runner_context(request_origin, subcommand, payload_path)
if error is not None:
    if subcommand == "ingest":
        error = _sanitize_user_facing_ingest_response(error)
        print(error.to_json())
        return _exit_code(error)
    if error.error_code == "parse_error" and error.message.startswith("Cannot read payload:"):
        print(json.dumps({"error": error.message}), file=sys.stderr)
        return 1
    print(error.to_json())
    return _exit_code(error)
```

After `dispatch_stage()`, keep the post-dispatch sanitization before the final `print(resp.to_json())`:

```python
resp = dispatch_stage(
    subcommand,
    context.payload,
    context.tickets_dir,
    context.request_origin,
)
if subcommand == "ingest":
    resp = _sanitize_user_facing_ingest_response(resp)
print(resp.to_json())
```

This split is intentional. `need_fields` from runner request shape, such as a missing `envelope_path` in the ingest request payload, means the saved preview state cannot be used and should get `retry_preview`. `need_fields` from `_dispatch_ingest()` after `read_envelope()` has populated `data.validation_errors` means the envelope contents failed checks and should get `preflight_failed`.

- [ ] **Step 4: Sanitize ingest policy messages before hints are attached**

In `_dispatch_ingest()`, replace user-facing policy messages that expose `envelope_path`, containment boundary paths, or raw `Got:` values with stable policy messages before they can receive `data.recovery_hint`:

```python
return EngineResponse(
    state="policy_blocked",
    message="Ticket ingest is blocked by Ticket policy.",
    error_code="policy_blocked",
)
```

Apply that shape to these current `_dispatch_ingest()` failure branches:

- envelope outside `.envelopes/`;
- envelope inside `.processed/`;
- envelope not a direct child of `.envelopes/`.

Also replace the duplicate/replay success message with:

```python
message="That Ticket ingest request was already processed; no ticket was created."
```

Do not attach `data.recovery_hint` to duplicate/replay success. Existing path fields in `data` remain machine/debug fields in raw stdout, and skills must not render them.

For the envelope-move partial-success branch, keep `ingest_outcome="created_envelope_move_failed"` and the existing machine/debug data fields, but replace the message with a transcript-safe partial-success summary:

```python
return EngineResponse(
    state=exec_resp.state,
    message="Ticket was created, but Ticket could not finish ingest cleanup.",
    ticket_id=exec_resp.ticket_id,
    data=data,
)
```

For the normal created-ingest branch, keep `ingest_outcome="created"` and the existing machine/debug data fields, but do not preserve `exec_resp.message` because create currently includes the ticket path. Replace it with:

```python
return EngineResponse(
    state=exec_resp.state,
    message="Ticket was created.",
    ticket_id=exec_resp.ticket_id,
    data=data,
)
```

Do not attach `data.recovery_hint` to successful mutation responses in this slice. The Handoff defer skill update below must render only the safe message, ticket ID, duplicate status, and user-safe success or partial-failure summary, not the path-bearing debug fields from raw stdout.

In `_dispatch()`, sanitize `PayloadError` responses for `subcommand == "ingest"` before returning them. This covers missing or malformed `envelope_path` from `IngestInput.from_payload()`:

```python
except PayloadError as exc:
    if subcommand == "ingest":
        return EngineResponse(
            state=exc.state,
            message=(
                "The saved preview state is no longer usable."
                if exc.code == "parse_error"
                else "Ticket ingest is blocked by Ticket policy."
            ),
            error_code=exc.code,
        )
    return EngineResponse(
        state=exc.state,
        message=f"{subcommand} payload validation failed: {exc}",
        error_code=exc.code,
    )
```

Keep detailed path diagnostics available only in raw machine `data`, low-level debug logs, or tests if needed; do not include them in `message`, `data.recovery_hint`, or the skill-rendered transcript projection.

- [ ] **Step 5: Preserve direct engine trust/debug behavior**

Do not rewrite `ticket_engine_core.py` trust/setup messages in this slice. Direct `classify`, `plan`, `preflight`, `execute`, and debug paths may remain technical, and existing direct-engine tests such as `plugins/turbo-mode/ticket/tests/test_execute.py::TestEngineExecute::test_execute_with_empty_session_id_rejected` may continue to assert low-level trust detail like `session_id empty`.

Wrapper-surfaced transcript safety must be handled in `ticket_capture.py`, `ticket_update.py`, and `ticket_engine_runner.py` by sanitizing the paired `message` before attaching `data.recovery_hint`. If implementation cannot satisfy the capture/update/ingest transcript-safety tests without changing `ticket_engine_core.py`, stop and revise this plan to include `plugins/turbo-mode/ticket/tests/test_execute.py` in the read-first list, file structure, focused tests, changed-path lint, and Commit 3 staging list before changing core behavior.

Keep low-level trust validation itself unchanged.

- [ ] **Step 6: Run ingest tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ingest.py -q
```

Expected: tests pass.

### Task 4: Add Doctor Cleanup Hint

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Test: `plugins/turbo-mode/ticket/tests/test_doctor.py`

- [ ] **Step 1: Locate existing stale-payload doctor tests**

```bash
rg -n "stale|clean-stale|ticket-tmp|payload" plugins/turbo-mode/ticket/tests/test_doctor.py plugins/turbo-mode/ticket/scripts/ticket_doctor.py
```

Expected: identify the existing diagnose and cleanup tests before editing.

- [ ] **Step 2: Add top-level diagnose response hint test**

Add a CLI-facing diagnose test so the hint is pinned to the user-facing response envelope, not to the raw `ticket_doctor()` report:

```python
def test_ticket_doctor_diagnose_response_adds_cleanup_hint_for_stale_payloads(
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
    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "diagnose",
            str(tickets_dir),
            "--plugin-root",
            str(plugin_root),
            "--cache-root",
            str(plugin_root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["state"] == "ok"
    assert response["data"]["report"]["payloads"]["stale_count"] == 1
    assert response["data"]["recovery_hint"] == {
        "code": "cleanup_stale_preview",
        "summary": "Old abandoned Ticket preview state can be cleaned up after review.",
        "next_step": "Use ticket-doctor stale cleanup after reviewing the reported items.",
    }
```

Keep the existing raw `ticket_doctor(...)` stale report test focused on report data. Do not add `recovery_hint` to `ticket_doctor()` report output or to `diagnose_payload()` directly.

When the top-level diagnose response reports stale temp payloads, assert:

```python
assert response["data"]["recovery_hint"] == {
    "code": "cleanup_stale_preview",
    "summary": "Old abandoned Ticket preview state can be cleaned up after review.",
    "next_step": "Use ticket-doctor stale cleanup after reviewing the reported items.",
}
```

Do not require cleanup to run in the diagnostic test.

- [ ] **Step 3: Run doctor tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_doctor.py -q
```

Expected: new hint assertion fails.

- [ ] **Step 4: Attach cleanup hint to the top-level diagnose response**

In `ticket_doctor.py`, import `attach_recovery_hint`. Leave `ticket_doctor()` and `diagnose_payload()` raw payload/report shapes unchanged. In the `diagnose` CLI branch, build the top-level response envelope first, then attach the hint only when the response envelope contains stale payload findings:

```python
response = _response("ok", payload)
if response["data"]["report"]["payloads"]["stale_count"] > 0:
    response = attach_recovery_hint(response, "cleanup_stale_preview")
print(json.dumps(response))
```

Only attach this hint when stale temp payloads are actually present. The durable contract is `response["data"]["recovery_hint"]` on the top-level diagnose response envelope.

- [ ] **Step 5: Run doctor tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_doctor.py -q
```

Expected: tests pass.

### Task 5: Update Skills And Contract Docs

**Files:**
- Modify: `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/handoff/skills/defer/SKILL.md`
- Modify: `plugins/turbo-mode/handoff/references/skill-details.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Test: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Test: `plugins/turbo-mode/handoff/tests/test_skill_docs.py`

- [ ] **Step 0: Resolve instruction-doc writing principles**

Before editing `SKILL.md` files or instruction-style references, read and apply the available `writing-principles` skill. Prefer the repo-local `.codex/skills/writing-principles/SKILL.md`; if it is absent in this checkout, use `/Users/jp/.agents/skills/writing-principles/SKILL.md`. If neither path exists or the skill cannot be read, stop and report that the repo instruction-doc quality gate cannot be satisfied.

- [ ] **Step 1: Add failing Ticket docs contract tests**

In `test_docs_contract.py`, assert the current-facing docs and skills describe `recovery_hint` as the preferred transcript surface:

```python
def test_user_facing_ticket_skills_prefer_recovery_hint() -> None:
    for path in [CAPTURE_SKILL, UPDATE_SKILL, DOCTOR_SKILL]:
        text = _normalize_whitespace(_read_text(path))
        assert "`data.recovery_hint`" in text
        assert "show the recovery summary and next step" in text
        assert "Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields" in text


def test_contract_documents_recovery_hint_schema_and_codes() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    docs = {
        "ticket-contract.md": contract,
        "HANDBOOK.md": handbook,
    }
    for name, text in docs.items():
        assert "`data.recovery_hint`" in text, name
        for code in [
            "stale_plan",
            "trust_setup",
            "retry_preview",
            "cleanup_stale_preview",
            "policy_blocked",
            "preflight_failed",
        ]:
            assert f"`{code}`" in text, name
        assert "safe to show directly to a human user" in text, name
        assert "Ingest stdout is a machine-readable JSON envelope" in text, name
        assert "allowlisted projection" in text, name
```

- [ ] **Step 2: Add failing Handoff defer transcript-boundary docs test**

In `plugins/turbo-mode/handoff/tests/test_skill_docs.py`, add:

```python
def test_defer_skill_hides_ticket_ingest_transcript_internals() -> None:
    skill = (PLUGIN_ROOT / "skills" / "defer" / "SKILL.md").read_text(encoding="utf-8")
    details = (PLUGIN_ROOT / "references" / "skill-details.md").read_text(encoding="utf-8")
    normalized_skill = " ".join(skill.split())
    normalized_details = " ".join(details.split())
    hidden_mechanics_sentence = (
        "Do not report Ticket ingest payload paths, processed envelope paths, "
        "incoming envelope paths, or envelope provenance in the human transcript."
    )
    render_only_sentence = (
        "Parse Ticket ingest JSON stdout and render only recovery summaries, "
        "next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, "
        "and user-safe ingest outcome prose."
    )

    assert "When Ticket ingest returns `data.recovery_hint`, show the recovery summary and next step" in normalized_skill
    assert render_only_sentence in normalized_skill
    assert render_only_sentence in normalized_details
    assert hidden_mechanics_sentence in normalized_skill
    assert hidden_mechanics_sentence in normalized_details
    assert "duplicate candidate ticket IDs" in normalized_details
    assert "Report ticket IDs, file paths, envelope provenance" not in normalized_skill
    assert "report ticket IDs, paths, processed envelopes" not in normalized_details
```

- [ ] **Step 3: Run docs tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_skill_docs.py -q
```

Expected: new Ticket and Handoff docs assertions fail.

- [ ] **Step 4: Patch `ticket-capture` skill**

In `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`, add an error handling section:

```markdown
## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `stale_plan`: say the preview is no longer current; rerun prepare and ask for
  confirmation again.
- `retry_preview`: say the saved preview state is no longer usable; rerun
  prepare and ask for confirmation again.
- `trust_setup`: stop without writing; say Ticket setup needs attention and
  suggest ticket-doctor diagnostics or plugin hook setup verification. The
  phrase "plugin hook setup" is allowed setup-level language; do not include
  hook/provenance field names or command-shape repair.
- `policy_blocked`: stop without writing; say the write is blocked by Ticket
  policy and the request or policy must change before retrying.
- `preflight_failed`: stop without writing; ask the user to review the check
  details, adjust the request, and rerun the preview.
```

- [ ] **Step 5: Patch `ticket-update` skill**

Add the same section, but allow ticket-specific context:

```markdown
For `stale_plan`, include the ticket ID when available: "Ticket <id> changed
since preview; rerun the preview against the current ticket, then confirm
again."
```

- [ ] **Step 6: Patch `ticket-doctor` skill**

Add:

```markdown
## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `cleanup_stale_preview`: say old abandoned Ticket preview state can be cleaned
  up after review. Do not clean anything until the user explicitly approves the
  confirmed cleanup command.
```

- [ ] **Step 7: Patch Handoff `defer` skill**

In `plugins/turbo-mode/handoff/skills/defer/SKILL.md`, keep the internal ingest command steps, but add a transcript-boundary section near the ingest/reporting steps:

```markdown
## Ticket Ingest Transcript Boundary

When Ticket ingest returns `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not report Ticket ingest payload paths, processed envelope paths, incoming envelope paths, or envelope provenance in the human transcript.

Parse Ticket ingest JSON stdout and render only recovery summaries, next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, and user-safe ingest outcome prose.

Report ticket IDs, duplicate candidates, and user-safe partial-failure summaries. For `created_envelope_move_failed`, say the ticket was created but ingest cleanup could not finish; suggest Ticket diagnostics before retrying cleanup. Never paste the raw Ticket ingest JSON into the human transcript.
```

Also change the reporting step so it no longer tells the worker to report file paths or envelope provenance. Keep path-specific staging instructions internal to the skill steps.

- [ ] **Step 8: Patch Handoff `skill-details` reference**

In `plugins/turbo-mode/handoff/references/skill-details.md`, replace the ingest reporting sentence with:

```markdown
On ingest: Parse Ticket ingest JSON stdout and render only recovery summaries, next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, and user-safe ingest outcome prose. Do not report Ticket ingest payload paths, processed envelope paths, incoming envelope paths, or envelope provenance in the human transcript.
```

- [ ] **Step 9: Patch contract docs**

In `ticket-contract.md`, add a compact subsection under the engine interface:

````markdown
### Recovery Hints

User-facing mutation and recovery surfaces may include `data.recovery_hint`.
When present, it is safe to show directly to a human user. The schema is:

```json
{"code": "stale_plan", "summary": "One user-safe sentence.", "next_step": "One concrete recovery action."}
```

Valid codes are `stale_plan`, `trust_setup`, `retry_preview`,
`cleanup_stale_preview`, `policy_blocked`, and `preflight_failed`.
Low-level direct engine/debug surfaces may remain technical unless their output
bubbles into a user-facing wrapper.

The whole object is transcript-safe. Do not add recovery hint codes that contain
hidden implementation mechanics. `plugin hook setup` is allowed as setup-level
recovery wording for `trust_setup`; hook/provenance field names and command
repair instructions remain internal.

Ingest stdout is a machine-readable JSON envelope. Skills and transcript-facing
workflows must parse it and render only the allowlisted projection: recovery
summary, recovery next step, safe message, ticket ID, duplicate candidate ticket
ID, and user-safe ingest outcome prose. Raw `data` fields such as processed
paths, incoming envelope paths, and envelope provenance are not transcript
fields.
````

In `HANDBOOK.md`, mirror this in the operator section and keep the lower-level trust/debug details intact.

- [ ] **Step 10: Run docs tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_skill_docs.py -q
```

Expected: Ticket docs contract tests and Handoff skill docs tests pass.

### Task 6: Focused Verification And Scope Review

**Files:**
- Review: all files modified in Tasks 1-5.

- [ ] **Step 1: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_ux.py \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  tests/test_ingest.py \
  tests/test_doctor.py \
  tests/test_docs_contract.py \
  -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/handoff pytest tests/test_skill_docs.py -q
```

Expected: all selected Ticket tests and Handoff skill docs tests pass.

- [ ] **Step 2: Run full Ticket tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: all Ticket tests pass.

- [ ] **Step 3: Run changed-path lint**

Adjust the file list to match the actual changed Python files:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/tests/test_ux.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/handoff/tests/test_skill_docs.py
```

Expected: no ruff failures.

- [ ] **Step 4: Run whitespace check**

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Review forbidden-scope diff**

```bash
git diff --stat
git diff -- plugins/turbo-mode/ticket plugins/turbo-mode/handoff docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md
```

Expected:
- source-local diff is limited to the planned Ticket/Handoff source, docs, and tests;
- no source-side installed-cache paths, personal-plugin sync outputs, app-server runtime inventory artifacts, live hook smoke artifacts, or runtime-readiness proof files are added;
- no new lock/queue/daemon;
- no `audience` field in `recovery_hint`;
- no user-facing recovery text or transcript projection that exposes `hook_injected`, `hook_request_origin`, `request_origin`, `origin_mismatch`, `PAYLOAD_PATH`, `payload`, `payload path`, `payload_file`, `envelope_path`, `processed_path`, `incoming_envelope_path`, `ticket_path`, `envelope_move_error`, raw absolute temp/workspace paths, canonical command repair, or `python3 -B`.

- This diff review is source-local evidence only. It does not prove installed-cache or app-server runtime state. If runtime proof is later required, run it as a separate non-mutating inventory slice.

- [ ] **Step 6: Commit according to the active boundary**

If the user asks to commit during implementation, use the five commit boundaries above. Before each commit, run `git status --short --branch`, review `git diff --stat`, and inspect the relevant diff. Stage only files in the active boundary.

Commit 2 example:

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git commit -m "fix(ticket): add recovery hint taxonomy"
```

Commit 3 example:

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py
git commit -m "fix(ticket): add transcript-safe mutation recovery hints"
```

Commit 4 example:

```bash
git add \
  plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md \
  plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md \
  plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md \
  plugins/turbo-mode/handoff/skills/defer/SKILL.md \
  plugins/turbo-mode/handoff/references/skill-details.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/handoff/tests/test_skill_docs.py
git commit -m "docs(ticket): document transcript-safe recovery hints"
```

Commit 5 example:

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py
git commit -m "fix(ticket): add stale preview cleanup recovery hint"
```

Expected: boundary commits are split as above unless the user explicitly asks for a single commit or squash.

## Self-Review Checklist

- [ ] Every user decision from the grill session is represented in a task or stop condition.
- [ ] `recovery_hint` schema has only `code`, `summary`, and `next_step`.
- [ ] Hint codes are limited to the six frozen codes and contain no hidden implementation mechanics such as `payload` or `envelope`.
- [ ] Trust/setup next step stops the write and points to ticket-doctor or plugin hook setup verification, with `plugin hook setup` allowed only as setup-level recovery language.
- [ ] Temp current-preview retry and stale cleanup are separate codes.
- [ ] Policy and preflight remain separate codes.
- [ ] Ingest policy responses with hints use sanitized messages and do not quote `envelope_path`, containment boundaries, or raw paths.
- [ ] Ingest parse/read failures return a normal stdout response envelope with `retry_preview`.
- [ ] Ingest pre-dispatch context failures from `load_runner_context()` return sanitized stdout envelopes before printing.
- [ ] Ingest request-shape `need_fields` uses `retry_preview`, while envelope-content `need_fields` with validation errors uses `preflight_failed`.
- [ ] Raw ingest stdout is documented as a machine-readable JSON envelope, while Handoff and Ticket skills render only the allowlisted transcript projection.
- [ ] Normal created-ingest success uses `message="Ticket was created."` and does not leak `ticket_path` through the allowlisted projection.
- [ ] Duplicate-candidate ingest keeps machine duplicate/fingerprint data in raw JSON only and proves the allowlisted projection is safe.
- [ ] Ingest envelope-move partial success has a safe message and no `recovery_hint` in this slice.
- [ ] Handoff `defer` reporting parses Ticket ingest JSON and renders only recovery summaries, next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, and user-safe ingest outcome prose.
- [ ] Handoff `defer` reporting does not expose Ticket ingest payload paths, processed envelope paths, incoming envelope paths, or envelope provenance.
- [ ] Docs tests normalize whitespace or snippets contain the exact asserted phrases.
- [ ] `origin_mismatch` remains the machine error code, but no user-facing message or transcript projection renders `origin_mismatch` or `request_origin` details.
- [ ] Direct engine/debug trust messages in `ticket_engine_core.py` remain technical unless this plan is explicitly revised with `tests/test_execute.py` coverage.
- [ ] `cleanup_stale_preview` is attached to the top-level `ticket_doctor.py diagnose` response envelope only; raw `ticket_doctor()` reports and `diagnose_payload()` payloads keep their existing shape.
- [ ] Transcript-safety tests assert the exact forbidden vocabulary set, including path-bearing data keys such as `processed_path`, `incoming_envelope_path`, `ticket_path`, and `envelope_move_error`, not just one matching term.
- [ ] Transcript-safety path tests cover known Mac, Linux CI, workspace-container, temp, var, and Windows absolute path shapes.
- [ ] `HANDBOOK.md` and `ticket-contract.md` both document the recovery-hint schema, frozen codes, and ingest projection boundary.
- [ ] Task 5 skill/reference edits read and apply the available `writing-principles` skill before modifying instruction docs.
- [ ] Task 0 stops on detached `HEAD` or any non-`fix/ticket-human-transcript-ux` branch unless the branch target is explicitly revised.
- [ ] The plan does not require installed-runtime proof.
- [ ] Source-local diff checks are worded as repo evidence only, not proof of external installed-cache or app-server runtime state.
- [ ] The plan does not require cache mutation or personal plugin sync.
- [ ] The plan does not introduce parallel serialization, locking, queueing, or runtime readiness.
- [ ] Implementation commits follow the five frozen boundaries unless the user explicitly asks for a single commit or squash.

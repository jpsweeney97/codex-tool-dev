# Ticket Human Transcript Recovery Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ticket's user-facing capture, update, ingest, and recovery paths explain recoverable failures in transcript-safe language without exposing payload mechanics, canonical command repair, or hook provenance internals.

**Architecture:** Treat the human transcript as the product boundary. Add a tiny shared recovery-hint taxonomy in `scripts/ticket_ux.py`, attach `data.recovery_hint` at user-facing mutation and recovery surfaces, keep backend `message` strings safe enough to quote for the selected common failures, and update skills so they prefer `recovery_hint` when present. Keep low-level direct engine/debug surfaces technical unless their response bubbles into `ticket_capture.py`, `ticket_update.py`, `ticket_engine_user.py ingest`, `ticket_engine_agent.py ingest`, or `ticket_doctor.py diagnose`.

**Tech Stack:** Python >=3.11, pytest, JSON response envelopes, Markdown skill docs, bytecode-safe `uv run` verification.

---

## Decision Freeze

These decisions are frozen for this implementation. If live source makes one impossible, stop and report the conflict before widening scope.

| Area | Frozen decision |
| --- | --- |
| Product boundary | The human transcript is the first-class interface. |
| Hidden mechanics | Payload files, canonical command shape, and hook provenance remain implementation details. |
| Structured hint | User-facing recoverable failures expose `data.recovery_hint`. |
| Hint safety | Whenever `data.recovery_hint` appears on a user-facing surface, it is safe to show directly to a human user. |
| Hint schema | `{"code": str, "summary": str, "next_step": str}` only. Do not add `audience` in this slice. |
| Hint codes | Only `stale_plan`, `trust_setup`, `retry_preview`, `cleanup_stale_payloads`, `policy_blocked`, and `preflight_failed`. |
| Trust/setup | Trust/setup failures stop the flow. They do not recommend bypassing the guard, changing command shape, or retrying blindly. |
| Temp state split | Use `retry_preview` for unusable current preview state. Use `cleanup_stale_payloads` only for old abandoned temp state reported by doctor. |
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
- `plugins/turbo-mode/ticket/scripts/ticket_payloads.py`
- `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`
- `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md`
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/tests/test_ux.py`
- `plugins/turbo-mode/ticket/tests/test_capture.py`
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- `plugins/turbo-mode/ticket/tests/test_ingest.py`
- `plugins/turbo-mode/ticket/tests/test_doctor.py`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

## File Structure

- `docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md` - this plan.
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py` - canonical recovery-hint taxonomy and safe attachment helpers.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - attach hints to capture prepare/execute recoverable failures.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - attach hints to update prepare/execute recoverable failures.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - attach hints for ingest and runner-level trust/setup or payload boundary failures.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` - make common trust/setup and stale-plan messages safe when they bubble through wrappers.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - attach `cleanup_stale_payloads` when stale temp payloads are reported.
- `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md` - tell the skill to render `recovery_hint` first and translate failures into user recovery.
- `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md` - same, with ticket-specific context.
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` - same, for stale cleanup reporting and confirmed cleanup.
- `plugins/turbo-mode/ticket/HANDBOOK.md` - operator-facing contract for `recovery_hint` without hiding lower-level debug docs.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - response contract for transcript-safe hints on user-facing surfaces.
- `plugins/turbo-mode/ticket/tests/test_ux.py` - taxonomy schema, exact wording, and internal-leak tests.
- `plugins/turbo-mode/ticket/tests/test_capture.py` - capture stale/retry/trust/policy hint coverage.
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py` - update stale/retry/trust/preflight hint coverage.
- `plugins/turbo-mode/ticket/tests/test_ingest.py` - ingest trust/setup and policy/preflight hint coverage.
- `plugins/turbo-mode/ticket/tests/test_doctor.py` - stale cleanup hint coverage.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` - static docs/skill contract checks.

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
    "cleanup_stale_payloads": {
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
    "verified hook provenance",
    "payload",
    "payload path",
    "payload_file",
    "envelope_path",
    "PAYLOAD_PATH",
    "canonical command",
    "python3 -B",
)

INTERNAL_RECOVERY_PATH_PATTERNS = (
    r"(?<![A-Za-z0-9_.-])/(?:Users|private|tmp|var)/",
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

The exact helper names may change during implementation if the surrounding code demands it, but the schema, codes, and user-safe text above are the contract.

## Stop Conditions

- If implementation needs to expose `hook_injected`, `hook_request_origin`, `PAYLOAD_PATH`, `payload`, `payload path`, `payload_file`, `envelope_path`, canonical command repair, raw absolute temp/workspace paths, or `python3 -B` in a user-facing `message` or `recovery_hint`, stop and redesign that path.
- If a user-facing response carries `data.recovery_hint`, the paired `message` must also avoid payload path mechanics, envelope path mechanics, canonical command repair, raw temp/workspace paths, and hook/provenance field names.
- If an ingest response gets `data.recovery_hint`, sanitize the paired `message` before attaching or printing the hint. Do not attach a hint to an ingest response whose message still quotes `envelope_path`, containment boundaries, or raw paths.
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
- Commit 4: skill/docs wording and docs contract tests.
- Commit 5: doctor stale cleanup hint tests and final verification, if not already covered by Commit 3 or 4.

---

### Task 0: Baseline And Branch Gate

**Files:**
- Read: `docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch is a non-`main` task branch, currently intended as `fix/ticket-human-transcript-ux`, and unrelated dirty work is preserved.

- [ ] **Step 2: If on `main`, create the implementation branch**

```bash
git branch --show-current
```

Expected: output is not `main`. If the output is `main`, run:

```bash
git switch -c fix/ticket-human-transcript-ux
```

Expected: branch switches to `fix/ticket-human-transcript-ux`.

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
```

Expected: all selected tests pass before changes, or failures are recorded before implementation.

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
    attach_recovery_hint,
    recovery_hint,
)
```

If imports already exist, add `import re` near the other stdlib imports and update the existing `from scripts.ticket_ux import ...` block instead of adding a second import later in the file.

Then add:

```python
def test_recovery_hint_contract_is_transcript_safe() -> None:
    hint = recovery_hint("trust_setup")

    assert hint == {
        "code": "trust_setup",
        "summary": "Ticket setup needs attention before this write can continue.",
        "next_step": (
            "Stop without writing. Run ticket-doctor diagnostics or verify the plugin "
            "hook setup before retrying."
        ),
    }
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


def test_transcript_safety_terms_cover_known_ingest_and_payload_leaks() -> None:
    rendered = (
        "envelope_path escapes containment boundary '/private/tmp/project/tickets/.envelopes'. "
        "Payload path must be absolute. Got: '/Users/example/project/.codex/ticket-tmp/payload.json'. "
        "Run python3 -B with hook_injected=True."
    )

    assert any(term.lower() in rendered.lower() for term in INTERNAL_RECOVERY_TERMS)
    assert any(re.search(pattern, rendered) for pattern in INTERNAL_RECOVERY_PATH_PATTERNS)
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
def _with_default_recovery_hint(response: dict[str, Any]) -> dict[str, Any]:
    code = recovery_hint_code_for_response(response)
    if code is None:
        return response
    return attach_recovery_hint(response, code)
```

Use it on responses returned from `_load_*_context()` and `dispatch_stage()` when those responses leave the user-facing wrapper.

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

For any capture/update response that carries `data.recovery_hint`, add or update tests so `_assert_hint()` covers the entire paired `message` plus hint. A response with a hint must not include `payload`, `Payload path`, `payload_file`, raw absolute temp/workspace paths, canonical command text, or hook/provenance field names.

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

- [ ] **Step 5: Run capture/update tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_capture.py \
  tests/test_update_refinement.py \
  -q
```

Expected: tests pass.

### Task 3: Attach Hints To Ingest And Runner Trust Setup

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Test: `plugins/turbo-mode/ticket/tests/test_ingest.py`

- [ ] **Step 1: Add ingest trust/setup, parse/read, and policy hint tests**

In `plugins/turbo-mode/ticket/tests/test_ingest.py`, add helpers that parse the JSON emitted by `run()` using `capsys` and assert the entire user-facing response is transcript-safe:

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


def _assert_user_response_safe(response: dict) -> None:
    rendered = json.dumps(
        {
            "message": response.get("message"),
            "recovery_hint": (response.get("data") or {}).get("recovery_hint"),
        },
        sort_keys=True,
    )
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
    _assert_user_response_safe(response)
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
    _assert_user_response_safe(response)
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
    _assert_user_response_safe(response)
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
    _assert_user_response_safe(response)
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
    _assert_user_response_safe(response)
    assert envelope_path.exists()
```

For existing containment and direct-child policy-blocked ingest tests, assert:

```python
assert response["data"]["recovery_hint"]["code"] == "policy_blocked"
assert response["message"] == "Ticket ingest is blocked by Ticket policy."
_assert_user_response_safe(response)
```

For the existing duplicate/replay test, keep the successful machine outcome but make the message safe:

```python
assert response["state"] == "ok"
assert response["data"]["ingest_outcome"] == "duplicate_replay"
assert "recovery_hint" not in response["data"]
assert response["message"] == "That Ticket ingest request was already processed; no ticket was created."
assert "envelope_path" not in response["message"]
```

- [ ] **Step 2: Run ingest tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_ingest.py -q
```

Expected: new recovery-hint, stdout-envelope, origin-code-preservation, and transcript-safety assertions fail.

- [ ] **Step 3: Attach runner-level hints**

In `ticket_engine_runner.py`, import:

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

For execute/ingest trust errors in `load_runner_context()`, keep `state="policy_blocked"` and `error_code="policy_blocked"`, but replace the message and attach `trust_setup`:

```python
return None, attach_engine_recovery_hint(
    EngineResponse(
        state="policy_blocked",
        message="Ticket setup needs attention before this write can continue.",
        error_code="policy_blocked",
    ),
    "trust_setup",
)
```

For ingest parse/read errors, remove the stderr-only `{"error": ...}` bypass. Keep the bypass for non-ingest debug stages if needed, but for `subcommand == "ingest"` return a normal JSON response envelope on stdout:

```python
if error.error_code == "parse_error" and subcommand == "ingest":
    error.message = "The saved preview state is no longer usable."
    error = attach_engine_recovery_hint(error, "retry_preview")
    print(error.to_json())
    return _exit_code(error)
```

Before printing responses from `run()` for `subcommand == "ingest"`, sanitize messages and attach default hints to policy/preflight/stale responses. If the response is an `EngineResponse`, use a helper like this:

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


if subcommand == "ingest":
    resp = _sanitize_user_facing_ingest_response(resp)
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

Do not attach `data.recovery_hint` to duplicate/replay success. Existing path fields in `data` remain machine/debug fields, and skills must not render them by default.

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

Keep detailed path diagnostics available only in low-level debug logs or tests if needed; do not include them in the user-facing response envelope when `data.recovery_hint` is attached.

- [ ] **Step 5: Make bubbling core trust messages safe**

In `ticket_engine_core.py`, for trust/setup failures that can bubble through user-facing wrappers, replace messages that enumerate hook fields with:

```python
message="Ticket setup needs attention before this write can continue."
```

Attach `trust_setup` through `attach_engine_recovery_hint()` when creating those responses. Do not remove low-level trust validation itself.

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

- [ ] **Step 2: Add or extend stale diagnostic test**

When doctor reports stale temp payloads, assert:

```python
assert response["data"]["recovery_hint"] == {
    "code": "cleanup_stale_payloads",
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

- [ ] **Step 4: Attach cleanup hint in doctor diagnostics**

In `ticket_doctor.py`, import `attach_recovery_hint`. When diagnostic response data includes stale payload findings, attach:

```python
response = attach_recovery_hint(response, "cleanup_stale_payloads")
```

Only attach this hint when stale temp payloads are actually present.

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
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Test: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Add failing docs contract tests**

In `test_docs_contract.py`, assert the current-facing docs and skills describe `recovery_hint` as the preferred transcript surface:

```python
def test_user_facing_skills_prefer_recovery_hint() -> None:
    for path in [CAPTURE_SKILL, UPDATE_SKILL, DOCTOR_SKILL]:
        text = _read_text(path)
        assert "`data.recovery_hint`" in text
        assert "show the recovery summary and next step" in text
        assert "Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields" in text


def test_contract_documents_recovery_hint_schema_and_codes() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    assert "`data.recovery_hint`" in contract
    for code in [
        "stale_plan",
        "trust_setup",
        "retry_preview",
        "cleanup_stale_payloads",
        "policy_blocked",
        "preflight_failed",
    ]:
        assert f"`{code}`" in contract
    assert "safe to show directly to a human user" in contract
```

- [ ] **Step 2: Run docs tests and verify they fail**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
```

Expected: new docs assertions fail.

- [ ] **Step 3: Patch `ticket-capture` skill**

In `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`, add an error handling section:

```markdown
## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery
summary and next step before any lower-level message. Do not expose payload
paths, envelope paths, canonical command repair, raw temp/workspace paths, or
hook/provenance fields in the transcript.

- `stale_plan`: say the preview is no longer current; rerun prepare and ask for
  confirmation again.
- `retry_preview`: say the saved preview state is no longer usable; rerun
  prepare and ask for confirmation again.
- `trust_setup`: stop without writing; say Ticket setup needs attention and
  suggest ticket-doctor diagnostics or plugin hook setup verification.
- `policy_blocked`: stop without writing; say the write is blocked by Ticket
  policy and the request or policy must change before retrying.
- `preflight_failed`: stop without writing; ask the user to review the check
  details, adjust the request, and rerun the preview.
```

- [ ] **Step 4: Patch `ticket-update` skill**

Add the same section, but allow ticket-specific context:

```markdown
For `stale_plan`, include the ticket ID when available: "Ticket <id> changed
since preview; rerun the preview against the current ticket, then confirm
again."
```

- [ ] **Step 5: Patch `ticket-doctor` skill**

Add:

```markdown
When diagnostics return `data.recovery_hint.code:
cleanup_stale_payloads`, show the summary and next step. Do not clean anything
until the user explicitly approves the confirmed cleanup command.
```

- [ ] **Step 6: Patch contract docs**

In `ticket-contract.md`, add a compact subsection under the engine interface:

````markdown
### Recovery Hints

User-facing mutation and recovery surfaces may include `data.recovery_hint`.
When present, it is safe to show directly to a human user. The schema is:

```json
{"code": "stale_plan", "summary": "One user-safe sentence.", "next_step": "One concrete recovery action."}
```

Valid codes are `stale_plan`, `trust_setup`, `retry_preview`,
`cleanup_stale_payloads`, `policy_blocked`, and `preflight_failed`.
Low-level direct engine/debug surfaces may remain technical unless their output
bubbles into a user-facing wrapper.
````

In `HANDBOOK.md`, mirror this in the operator section and keep the lower-level trust/debug details intact.

- [ ] **Step 7: Run docs tests and verify they pass**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
```

Expected: docs contract tests pass.

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
```

Expected: all selected tests pass.

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
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/tests/test_ux.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
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
git diff -- plugins/turbo-mode/ticket scripts docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md
```

Expected:
- no installed-cache mutation;
- no app-server runtime inventory;
- no live hook smoke or runtime-readiness proof file;
- no new lock/queue/daemon;
- no `audience` field in `recovery_hint`;
- no user-facing recovery text that exposes `hook_injected`, `hook_request_origin`, `PAYLOAD_PATH`, `payload`, `payload path`, `payload_file`, `envelope_path`, raw absolute temp/workspace paths, canonical command repair, or `python3 -B`.

- [ ] **Step 6: Commit coherent result**

If the user asks to commit, stage only the files changed for this plan and commit with:

```bash
git add \
  docs/superpowers/plans/2026-05-19-ticket-human-transcript-recovery-hints.md \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md \
  plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md \
  plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/tests/test_ux.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "fix(ticket): add transcript-safe recovery hints"
```

Expected: one coherent source-local commit if commit approval is in scope.

## Self-Review Checklist

- [ ] Every user decision from the grill session is represented in a task or stop condition.
- [ ] `recovery_hint` schema has only `code`, `summary`, and `next_step`.
- [ ] Hint codes are limited to the six frozen codes.
- [ ] Trust/setup next step stops the write and points to ticket-doctor or hook setup verification.
- [ ] Temp current-preview retry and stale cleanup are separate codes.
- [ ] Policy and preflight remain separate codes.
- [ ] Ingest policy responses with hints use sanitized messages and do not quote `envelope_path`, containment boundaries, or raw paths.
- [ ] Ingest parse/read failures return a normal stdout response envelope with `retry_preview`.
- [ ] Ingest request-shape `need_fields` uses `retry_preview`, while envelope-content `need_fields` with validation errors uses `preflight_failed`.
- [ ] `origin_mismatch` remains the machine error code and only gains `trust_setup`.
- [ ] Transcript-safety tests cover lower-case payload wording, `payload_file`, `envelope_path`, canonical command text, hook/provenance fields, and raw absolute temp/workspace paths.
- [ ] The plan does not require installed-runtime proof.
- [ ] The plan does not require cache mutation or personal plugin sync.
- [ ] The plan does not introduce parallel serialization, locking, queueing, or runtime readiness.

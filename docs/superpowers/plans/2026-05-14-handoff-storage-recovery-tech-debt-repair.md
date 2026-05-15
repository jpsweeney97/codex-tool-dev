# Handoff Storage Recovery Tech Debt Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Handoff 1.6.0 recovery and diagnostic paths against corrupt state files, parser drift, non-portable cleanup, and import bootstrap shadowing while preserving existing runtime contracts.

**Architecture:** Ship correctness and recovery fixes first, then structural cleanup. Shared low-level filesystem behavior belongs in `storage_primitives.py`; domain-specific error messages stay in the caller modules that already own `ActiveWriteError`, `LoadTransactionError`, `ValueError`, and `ChainStateDiagnosticError`. Bootstrap consolidation is isolated in the final task because it touches import resolution and installed-host isolation.

**Tech Stack:** Python 3.11+ standard library only; POSIX filesystem semantics for atomic hard-link publishing; existing Handoff pytest suite; bytecode-free commands with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPYCACHEPREFIX`, and `-p no:cacheprovider`.

---

## Base State

Re-check these before implementation:

```bash
git status --short --branch
git rev-parse --short HEAD
git rev-parse --abbrev-ref HEAD
```

**Branch gate (run before any commit step in any task).** This repository protects `main`. The user's convention is `fix/*` for bug fixes and `chore/*` for maintenance. If `git rev-parse --abbrev-ref HEAD` reports `main` (or any other protected branch), create the working branch first:

```bash
git checkout -b fix/handoff-storage-recovery-tech-debt main
```

If the worker is already on a feature branch (e.g. resuming this plan mid-execution), stay on that branch. Never run `git checkout main` only to commit there. Never bypass `--no-verify`, `--no-gpg-sign`, or signing hooks. If a hook fails, fix the underlying issue and create a new commit; do not amend pushed commits.

The plan assumes the current Handoff plugin lives at:

`plugins/turbo-mode/handoff/1.6.0/`

Relevant current files:

- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py`
  - Owns atomic JSON writes, SHA helpers, timestamp parsing, and lock primitives.
- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
  - Still raw-parses operation state at existing reservation, write, abandon, and recovery entry points.
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
  - Still raw-parses registry files through `_read_registry`.
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
  - Still raw-parses resume state in list, migration reread, and clear paths.
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
  - Recovery inventory can fail on corrupt chain-state marker.
  - Active selection can fail on corrupt consumed-legacy-active registry.
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
  - Has a local section parser with weaker fence tracking than `handoff_parsing.py`.
- `plugins/turbo-mode/handoff/1.6.0/scripts/defer.py`
  - Writes envelope JSON with exclusive create but without temp-file atomicity.

## Non-Goals

Do not include these in this repair series:

- Batched git visibility or lazy SHA performance work.
- Transaction archival or state-file rotation.
- `StorageLocation` / `SelectionEligibility` enum redesign.
- `layout` type annotation sweep.
- Broad load/active-write state-machine refactor.
- Installed cache, publication, or Gate 5 certification claims.
- Any deletion command using `rm`.
- Windows filesystem compatibility for atomic exclusive envelope writes; `write_text_atomic_exclusive` assumes `os.link` works on the target filesystem.

## Commit Boundaries

Use one commit per task:

1. `fix: add handoff JSON and text file primitives`
2. `fix: handle corrupt handoff state reads`
3. `fix: keep handoff recovery inventories readable`
4. `fix: share handoff section parsing`
5. `fix: make handoff state cleanup portable`
6. `chore: consolidate handoff script bootstrap`

Stop after Task 5 if runtime correctness is the immediate release target. Task 6 is intentionally separated because import bootstrapping has a larger test matrix.

## File Structure

Create:

- `plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py`
  - Final-task shared import repair for direct script execution and shadowed parent processes.

Modify:

- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py`
  - Add JSON object read primitive.
  - Add atomic exclusive text write primitive.
  - Add portable delete primitive.
- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
  - Replace raw operation-state JSON reads.
  - Use portable delete primitive for primary state cleanup.
  - In final task, replace heavyweight import fallback with shared bootstrap.
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
  - Replace raw registry JSON reads.
  - In final task, replace heavyweight import fallback with shared bootstrap.
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
  - Replace raw resume-state JSON reads.
  - Use portable delete primitive for clear/prune/migration cleanup.
  - In final task, replace import fallback with shared bootstrap.
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
  - Degrade marker and consumed-registry failures on listing/selection surfaces.
  - In final task, replace heavyweight import fallback with shared bootstrap.
- `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py`
  - Upgrade `parse_sections` to recognize 1-3 space indented fences (CommonMark behavior already present in `quality_check.parse_sections`). Required before the wrapper swap so search/distill callers and `quality_check`'s existing indented-fence tests both stay green.
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
  - Delegate frontmatter/section parsing to `handoff_parsing.py` while preserving current return shapes.
- `plugins/turbo-mode/handoff/1.6.0/scripts/defer.py`
  - Use atomic exclusive text write primitive.
  - Task 5 introduces a `scripts.storage_primitives` import, so Task 6 must include `defer.py` in the bootstrap-prelude sweep.

Tests:

- `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_handoff_parsing.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_search.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_distill.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_defer.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_harness.py`

---

### Task 1: Shared JSON, Atomic Text, and Delete Primitives

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py`

- [ ] **Step 1: Add failing tests for JSON object reads**

Append these tests to `test_storage_primitives.py`:

```python
def test_read_json_object_returns_default_for_missing_path(tmp_path: Path) -> None:
    assert storage_primitives.read_json_object(
        tmp_path / "missing.json",
        missing={"entries": []},
    ) == {"entries": []}


def test_read_json_object_rejects_unreadable_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object unreadable"):
        storage_primitives.read_json_object(path)


def test_read_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object malformed"):
        storage_primitives.read_json_object(path)
```

- [ ] **Step 2: Add failing tests for atomic exclusive text writes**

Append:

```python
def test_write_text_atomic_exclusive_uses_suffix_without_replacing_existing(
    tmp_path: Path,
) -> None:
    first = tmp_path / "envelope.json"
    first.write_text("existing", encoding="utf-8")

    written = storage_primitives.write_text_atomic_exclusive(first, "new")

    assert written == tmp_path / "envelope-01.json"
    assert first.read_text(encoding="utf-8") == "existing"
    assert written.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("*.tmp"))


def test_write_text_atomic_exclusive_exhausts_collision_budget(tmp_path: Path) -> None:
    for index in range(100):
        suffix = "" if index == 0 else f"-{index:02d}"
        (tmp_path / f"envelope{suffix}.json").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="collision budget exhausted"):
        storage_primitives.write_text_atomic_exclusive(tmp_path / "envelope.json", "new")
```

- [ ] **Step 3: Add failing tests for portable delete**

Append:

```python
def test_safe_delete_uses_trash_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> object:
        calls.append(args)
        path.unlink()
        return object()

    monkeypatch.setattr(storage_primitives.subprocess, "run", fake_run)

    result = storage_primitives.safe_delete(path)

    assert result.action == "deleted"
    assert result.mechanism == "trash"
    assert result.path == str(path)
    assert calls == [["trash", str(path)]]
    assert not path.exists()


def test_safe_delete_falls_back_to_unlink_when_trash_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    monkeypatch.setattr(storage_primitives.subprocess, "run", fail_trash)

    result = storage_primitives.safe_delete(path)

    assert result.action == "deleted"
    assert result.mechanism == "unlink"
    assert result.path == str(path)
    assert not path.exists()


def test_safe_delete_reports_already_absent(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    result = storage_primitives.safe_delete(path)

    assert result.action == "already_absent"
    assert result.mechanism is None
    assert result.path == str(path)


def test_safe_delete_returns_failed_when_trash_and_unlink_both_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    original_unlink = Path.unlink

    def fail_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == path:
            raise PermissionError("unlink denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(storage_primitives.subprocess, "run", fail_trash)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    result = storage_primitives.safe_delete(path)

    assert result.action == "failed"
    assert result.mechanism == "unlink"
    assert result.path == str(path)
    assert result.error is not None
    assert "unlink" in result.error
    assert path.exists()
```

- [ ] **Step 4: Run primitive tests and verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py -q
```

Expected: failures for missing `read_json_object`, `write_text_atomic_exclusive`, `DeleteResult`, `safe_delete`, and `subprocess`.

- [ ] **Step 5: Implement primitives**

Add these imports and APIs to `storage_primitives.py`:

```python
import subprocess


@dataclass(frozen=True)
class DeleteResult:
    action: str
    mechanism: str | None
    path: str
    error: str | None = None


def read_json_object(
    path: Path,
    *,
    missing: dict[str, object] | None = None,
) -> dict[str, object]:
    """Read a JSON object from disk, optionally returning a missing-file default."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if missing is not None:
            return dict(missing)
        raise
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"read-json-object failed: JSON object unreadable. Got: {str(path)!r:.100}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"read-json-object failed: JSON object malformed. Got: {str(path)!r:.100}"
        )
    return payload


def write_text_atomic_exclusive(
    path: Path,
    payload: str,
    *,
    max_attempts: int = 100,
) -> Path:
    """Write text through a sibling temp file and publish via exclusive hard link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    suffix = path.suffix
    for attempt in range(max_attempts):
        retry_suffix = "" if attempt == 0 else f"-{attempt:02d}"
        candidate = path.with_name(f"{stem}{retry_suffix}{suffix}")
        temp_path = candidate.with_name(f".{candidate.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(payload, encoding="utf-8")
            try:
                os.link(temp_path, candidate)
            except FileExistsError:
                continue
            return candidate
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
    raise FileExistsError(
        f"write-text-atomic-exclusive failed: collision budget exhausted. Got: {str(path)!r:.100}"
    )


def safe_delete(path: Path) -> DeleteResult:
    """Delete one file by preferring trash, then unlink, then reporting failure.

    Returns a DeleteResult with action in {"deleted", "already_absent", "failed"}.
    Never raises for trash or unlink errors; callers inspect ``action`` to decide
    whether to enter their own recovery flow. ``mechanism`` records which delete
    path was attempted on success or partial-attempt; ``error`` carries the last
    underlying exception string on failure so callers can surface it in
    operator-actionable messages.
    """
    if not path.exists():
        return DeleteResult(action="already_absent", mechanism=None, path=str(path))
    try:
        subprocess.run(
            ["trash", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return DeleteResult(action="deleted", mechanism="trash", path=str(path))
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as trash_exc:
        try:
            path.unlink()
        except FileNotFoundError:
            return DeleteResult(action="already_absent", mechanism=None, path=str(path))
        except OSError as unlink_exc:
            return DeleteResult(
                action="failed",
                mechanism="unlink",
                path=str(path),
                error=f"trash: {trash_exc!r}; unlink: {unlink_exc!r}",
            )
        return DeleteResult(action="deleted", mechanism="unlink", path=str(path))
```

The `action="failed"` return path is what active-write cleanup uses to preserve the existing `cleanup_failed` recovery state. Task 5 Step 5 raises `ActiveWriteError` when it sees a non-success action, which then routes through the existing `except ActiveWriteError` block at `active_writes.py:565-584` and persists `cleanup_failed` to both the operation-state file and the transaction record.

- [ ] **Step 6: Run primitive tests and verify they pass**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py -q
```

Expected: all `test_storage_primitives.py` tests pass.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py
git commit -m "fix: add handoff JSON and text file primitives"
```

---

### Task 2: Defend Mutating JSON Reads

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`

- [ ] **Step 1: Add failing active-write tests**

Append to `test_active_writes.py`:

```python
def test_existing_reservation_reports_corrupt_operation_state(tmp_path: Path) -> None:
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    operation_state_path = state_dir / "active-writes" / "demo" / "run-1.json"
    operation_state_path.parent.mkdir(parents=True, exist_ok=True)
    operation_state_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(active_writes.ActiveWriteError, match="operation state unreadable"):
        active_writes.begin_active_write(
            tmp_path,
            project_name="demo",
            operation="save",
            run_id="run-1",
            created_at="2026-05-14T00:00:00Z",
        )


def test_write_active_handoff_reports_corrupt_operation_state(tmp_path: Path) -> None:
    operation_state_path = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "active-writes" / "demo" / "run-2.json"
    )
    operation_state_path.parent.mkdir(parents=True, exist_ok=True)
    operation_state_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(active_writes.ActiveWriteError, match="operation state unreadable"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=operation_state_path,
            content="content",
            content_sha256=hashlib.sha256(b"content").hexdigest(),
        )
```

- [ ] **Step 2: Add failing load registry test**

Append to `test_load_transactions.py`:

```python
def test_read_registry_reports_corrupt_json(tmp_path: Path) -> None:
    registry_path = tmp_path / ".codex" / "handoffs" / ".session-state" / "copied-legacy-archives.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(load_transactions.LoadTransactionError, match="registry unreadable"):
        load_transactions._read_registry(registry_path)
```

- [ ] **Step 3: Add failing session-state tests**

Append to `test_session_state.py`:

```python
def test_list_resume_states_reports_corrupt_json(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    (state_dir / "handoff-demo-bad.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(session_state.CorruptResumeStateError, match="resume state unreadable"):
        session_state.list_resume_states(state_dir, "demo")


def test_clear_resume_state_reports_corrupt_json(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    state_path = state_dir / "handoff-demo-bad.json"
    state_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(session_state.CorruptResumeStateError, match="resume state unreadable"):
        session_state.clear_resume_state(state_dir, str(state_path))
```

- [ ] **Step 4: Run focused tests and verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py::test_existing_reservation_reports_corrupt_operation_state \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py::test_write_active_handoff_reports_corrupt_operation_state \
  plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py::test_read_registry_reports_corrupt_json \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py::test_list_resume_states_reports_corrupt_json \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py::test_clear_resume_state_reports_corrupt_json -q
```

Expected: failures showing raw `JSONDecodeError`, missing helper behavior, or message mismatch.

- [ ] **Step 5: Add caller-owned read wrappers**

In `active_writes.py`, import `read_json_object` as `_read_json_object` from `storage_primitives.py`, then add:

```python
def _read_operation_state(path: Path, *, operation_label: str) -> dict[str, object]:
    try:
        return _read_json_object(path)
    except (OSError, ValueError) as exc:
        raise ActiveWriteError(
            f"{operation_label} failed: operation state unreadable; manual operator review required. "
            f"Got: {str(path)!r:.100}"
        ) from exc
```

Use `_read_operation_state` at the current raw reads in `_existing_reservation`, `write_active_handoff`, `abandon_active_write`, and `recover_active_write_transaction`.

In `load_transactions.py`, import `read_json_object` as `_read_json_object`, then replace `_read_registry` with:

```python
def _read_registry(path: Path) -> dict[str, object]:
    try:
        data = _read_json_object(path, missing={"entries": []})
    except (OSError, ValueError) as exc:
        raise LoadTransactionError(
            "load-handoff failed: registry unreadable; manual operator review required. "
            f"Got: {str(path)!r:.100}"
        ) from exc
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise LoadTransactionError(
            f"load-handoff failed: invalid copied legacy archive registry. Got: {str(path)!r:.100}"
        )
    return data
```

In `session_state.py`, import `read_json_object`, then add a distinct stored-state corruption exception near `AmbiguousResumeStateError`:

```python
class CorruptResumeStateError(RuntimeError):
    pass
```

Update the `read-state` CLI dispatcher to catch it with the existing recoverable state errors:

```python
except (AmbiguousResumeStateError, CorruptResumeStateError, ValueError) as exc:
    json.dump({"error": str(exc)}, sys.stdout)
    return 2
```

Update the `clear-state` CLI dispatcher at `session_state.py:427-430` to catch the same exception class. After Task 2, `clear_resume_state` reads stored state via the wrapper, so a corrupt resume-state file would otherwise escape as an unhandled traceback. Wrap the call:

```python
if args.command == "clear-state":
    try:
        cleared = clear_resume_state(Path(args.state_dir), args.state_path)
    except CorruptResumeStateError as exc:
        json.dump({"error": str(exc)}, sys.stdout)
        return 2
    return 0 if cleared else 1
```

Audit other dispatchers that indirectly reach `list_resume_states`, `migrate_legacy_resume_state`, or `clear_resume_state` (notably any subcommand that lists existing state files before deciding what to clear) and apply the same catch. `read-state` and `clear-state` are the load-bearing pair; if a worker finds an additional reachable site, add it here in the same task.

Then add:

```python
def _read_resume_state_payload(path: Path, *, operation: str) -> dict[str, object]:
    try:
        return read_json_object(path)
    except (OSError, ValueError) as exc:
        raise CorruptResumeStateError(
            f"{operation} failed: resume state unreadable. Got: {str(path)!r:.100}"
        ) from exc
```

Use `_read_resume_state_payload` in `list_resume_states`, `migrate_legacy_resume_state`, and `clear_resume_state`. Keep existing `ValueError` raises for caller-input problems such as empty paths, wrong filename patterns, non-file paths, and state-dir escapes.

- [ ] **Step 6: Run focused tests and verify they pass**

Run the same command from Step 4.

Expected: all focused tests pass.

- [ ] **Step 7: Run touched module tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py
git commit -m "fix: handle corrupt handoff state reads"
```

---

### Task 3: Keep Recovery Inventories Readable

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`

- [ ] **Step 1: Add failing marker-degradation test**

Append to `test_storage_authority.py`:

```python
def test_chain_state_recovery_inventory_degrades_on_corrupt_marker(tmp_path: Path) -> None:
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-token.json"
    state_path.write_text(
        json.dumps({
            "project": "demo",
            "resume_token": "token",
            "archive_path": str(tmp_path / "archive.md"),
            "created_at": "2026-05-14T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    marker_path = state_dir / "markers" / "chain-state-consumed.json"
    marker_path.parent.mkdir()
    marker_path.write_text("{bad", encoding="utf-8")

    inventory = chain_state_recovery_inventory(
        tmp_path,
        project_name="demo",
    )

    assert inventory["total"] == 1
    assert inventory["candidates"][0]["marker_status"] == "marker-unreadable"
```

- [ ] **Step 2: Add failing consumed-registry degradation test**

Append:

```python
def test_active_inventory_degrades_on_corrupt_consumed_legacy_active_registry(
    tmp_path: Path,
) -> None:
    legacy_dir = tmp_path / "docs" / "handoffs"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "2026-05-14_00-00_demo.md"
    legacy.write_text(
        "---\nproject: demo\ncreated_at: 2026-05-14T00:00:00Z\nsession_id: s\ntype: handoff\n---\n\n## Goal\nbody\n",
        encoding="utf-8",
    )
    registry = tmp_path / ".codex" / "handoffs" / ".session-state" / "consumed-legacy-active.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{bad", encoding="utf-8")

    inventory = discover_handoff_inventory(
        tmp_path,
        scan_mode="active-selection",
    )

    candidates = [candidate for candidate in inventory.candidates if candidate.path == legacy.resolve()]
    assert len(candidates) == 1
    assert candidates[0].selection_eligibility == SelectionEligibility.BLOCKED_POLICY_CONFLICT
    assert candidates[0].skip_reason == "consumed legacy active registry unreadable"
```

- [ ] **Step 3: Run focused tests and verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py::test_chain_state_recovery_inventory_degrades_on_corrupt_marker \
  plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py::test_active_inventory_degrades_on_corrupt_consumed_legacy_active_registry -q
```

Expected: first test raises `ChainStateDiagnosticError`; second test raises `ChainStateDiagnosticError` or returns a different eligibility.

- [ ] **Step 4: Implement marker degradation**

Change `_chain_state_marker_status` to catch marker read failures:

```python
def _chain_state_marker_status(
    layout: StorageLayout,
    candidate: dict[str, object],
) -> str:
    if candidate["validation_status"] not in {"valid", "expired"}:
        return "unmarked"
    marker_path = layout.primary_state_dir / "markers" / "chain-state-consumed.json"
    if not marker_path.exists():
        # Preserve current behavior: "no marker file yet" is the normal pre-consumption
        # state and must remain `unmarked`. Only present-but-malformed markers escalate
        # to `marker-unreadable`.
        return "unmarked"
    try:
        marker = _read_json_object(marker_path)
    except ChainStateDiagnosticError as exc:
        error = exc.payload.get("error", {})
        code = error.get("code") if isinstance(error, dict) else ""
        if code in {"chain-state-marker-unreadable", "chain-state-marker-malformed"}:
            return "marker-unreadable"
        raise
    entries = marker.get("entries")
    if not isinstance(entries, list):
        return "marker-unreadable"
    stable_key = _chain_state_stable_key(candidate)
    if any(
        isinstance(entry, dict) and entry.get("stable_key") == stable_key
        for entry in entries
    ):
        return "consumed"
    return "unmarked"
```

Add (or update) inventory tests in `test_storage_authority.py` to cover both branches:

```python
def test_chain_state_marker_status_returns_unmarked_when_marker_missing(
    tmp_path: Path,
) -> None:
    # Inventory of a project root with no marker file must produce
    # marker_status == "unmarked", not "marker-unreadable".
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-token.json"
    state_path.write_text(
        json.dumps({
            "project": "demo",
            "resume_token": "token",
            "archive_path": str(tmp_path / "archive.md"),
            "created_at": "2026-05-14T00:00:00+00:00",
        }),
        encoding="utf-8",
    )

    payload = chain_state_recovery_inventory(
        tmp_path,
        project_name="demo",
    )

    assert payload["total"] == 1
    assert payload["candidates"][0]["marker_status"] == "unmarked"


def test_chain_state_marker_status_returns_marker_unreadable_when_payload_malformed(
    tmp_path: Path,
) -> None:
    # Present-but-malformed marker (e.g., {"entries": "not-a-list"}) must
    # produce marker_status == "marker-unreadable", not "unmarked".
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-token.json"
    state_path.write_text(
        json.dumps({
            "project": "demo",
            "resume_token": "token",
            "archive_path": str(tmp_path / "archive.md"),
            "created_at": "2026-05-14T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    marker_path = state_dir / "markers" / "chain-state-consumed.json"
    marker_path.parent.mkdir()
    marker_path.write_text(json.dumps({"entries": "not-a-list"}), encoding="utf-8")

    payload = chain_state_recovery_inventory(
        tmp_path,
        project_name="demo",
    )

    assert payload["total"] == 1
    assert payload["candidates"][0]["marker_status"] == "marker-unreadable"
```

- [ ] **Step 5: Implement consumed-registry status instead of bool-only matching**

Replace `_consumed_legacy_active_matches` with a status helper:

```python
def _consumed_legacy_active_status(
    project_root: Path,
    path: Path,
    content_sha256: str,
) -> str:
    registry_path = (
        get_storage_layout(project_root).primary_state_dir / "consumed-legacy-active.json"
    )
    try:
        payload = _read_json_object_primitive(registry_path, missing={"entries": []})
    except (OSError, ValueError):
        return "registry-unreadable"
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return "registry-unreadable"
    expected = {
        "source_root": "project_root",
        "project_relative_source_path": path.relative_to(project_root).as_posix(),
        "storage_location": StorageLocation.LEGACY_ACTIVE,
        "source_content_sha256": content_sha256,
    }
    for entry in entries:
        if isinstance(entry, dict) and _registry_key(entry) == expected:
            return "consumed"
    return "not-consumed"
```

Import the shared primitive with a non-conflicting name because `storage_authority.py` already has a domain-specific `_read_json_object` helper that raises `ChainStateDiagnosticError` for marker files:

```python
from scripts.storage_primitives import (
    read_json_object as _read_json_object_primitive,
    sha256_regular_file_or_none as _content_sha256,
    write_json_atomic as _write_json_atomic,
)
```

In `_candidate_for_path`, call this helper once for legacy active selection. If it returns `"consumed"`, keep the existing consumed candidate behavior. If it returns `"registry-unreadable"`, return a blocked candidate:

```python
return HandoffCandidate(
    path=path.resolve(),
    storage_location=location,
    artifact_class="consumed-legacy-active-registry-unreadable",
    selection_eligibility=SelectionEligibility.BLOCKED_POLICY_CONFLICT,
    source_git_visibility=git_visibility,
    source_fs_status=fs_status,
    filename_timestamp=filename_timestamp,
    content_sha256=content_sha256,
    document_profile=document_profile,
    skip_reason="consumed legacy active registry unreadable",
)
```

- [ ] **Step 6: Run focused tests and verify they pass**

Run the command from Step 3.

Expected: both tests pass.

- [ ] **Step 7: Run storage authority tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py -q
```

Expected: all storage authority tests pass.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py
git commit -m "fix: keep handoff recovery inventories readable"
```

---

### Task 4: Share Handoff Section Parsing

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_handoff_parsing.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py`

- [ ] **Step 1: Add failing mixed-fence test**

Append to `test_quality_check.py`:

```python
def test_parse_sections_does_not_close_backtick_fence_with_tilde_fence() -> None:
    content = "\n".join([
        "---",
        "type: handoff",
        "---",
        "## A",
        "```",
        "~~~",
        "## inside",
        "```",
        "## B",
        "body",
        "",
    ])

    sections = parse_sections(content)

    assert [section["heading"] for section in sections] == ["A", "B"]
```

- [ ] **Step 2: Run the focused parser test and verify it fails**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py::test_parse_sections_does_not_close_backtick_fence_with_tilde_fence -q
```

Expected: failure showing `["A", "inside"]` or another incorrect section list.

- [ ] **Step 3: Upgrade `handoff_parsing.parse_sections` to recognize 1-3 space indented fences**

The shared parser at `handoff_parsing.py` currently checks `line.rstrip().startswith("```")`, which never matches a 3-space-indented fence. The local parser in `quality_check.py:158-164` already handles indented fences and has live test coverage at `tests/test_quality_check.py:293` (`test_ignores_headings_inside_indented_code_fences`). Swapping the wrapper without first upgrading the shared parser will fail those tests in Step 6.

Update `parse_sections` in `handoff_parsing.py` to match CommonMark indented-fence behavior while preserving its existing marker-type tracking:

```python
def parse_sections(text: str) -> list[Section]:
    """Split markdown text into ## sections.

    Recognizes both backtick (```) and tilde (~~~) fences. Per CommonMark,
    fences may be indented up to 3 spaces. The closing fence must use the
    same character as the opening fence; mixed-fence content stays inside
    the open fence.
    """
    sections: list[Section] = []
    lines = text.splitlines(keepends=True)
    current_heading = ""
    current_lines: list[str] = []
    inside_fence = False
    fence_marker = ""

    for line in lines:
        stripped_left = line.lstrip(" ")
        indent = len(line) - len(stripped_left)
        rstripped = stripped_left.rstrip()
        if (
            not inside_fence
            and indent <= 3
            and (rstripped.startswith("```") or rstripped.startswith("~~~"))
        ):
            inside_fence = True
            fence_marker = rstripped[:3]
        elif inside_fence and indent <= 3 and rstripped.startswith(fence_marker):
            inside_fence = False
            fence_marker = ""
        if not inside_fence and line.startswith("## "):
            if current_heading:
                content = "".join(current_lines).strip()
                sections.append(Section(
                    heading=current_heading,
                    level=2,
                    content=content,
                ))
            current_heading = line.strip()
            current_lines = []
        elif current_heading:
            current_lines.append(line)

    if current_heading:
        content = "".join(current_lines).strip()
        sections.append(Section(
            heading=current_heading,
            level=2,
            content=content,
        ))

    return sections
```

Add behavior tests to `tests/test_handoff_parsing.py` (create the file if missing — `handoff_parsing.py` is already a shared module used by `search.py` and `distill.py`, and warrants its own test surface):

```python
from scripts.handoff_parsing import parse_sections


def test_parse_sections_ignores_headings_inside_indented_code_fences() -> None:
    text = (
        "## A\n"
        "Some content\n"
        "   ```\n"
        "## Fake\n"
        "   ```\n"
        "## B\n"
        "Final\n"
    )
    sections = parse_sections(text)
    headings = [section.heading for section in sections]
    assert headings == ["## A", "## B"]


def test_parse_sections_does_not_close_backtick_fence_with_tilde_fence() -> None:
    text = (
        "## A\n"
        "```\n"
        "~~~\n"
        "## inside\n"
        "```\n"
        "## B\n"
        "body\n"
    )
    sections = parse_sections(text)
    headings = [section.heading for section in sections]
    assert headings == ["## A", "## B"]
```

Run the focused tests and the downstream callers to confirm no regression:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_handoff_parsing.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_search.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_distill.py -q
```

Expected: new indented-fence and mixed-fence tests pass; existing `search` and `distill` tests stay green.

- [ ] **Step 4: Import shared parser with direct-execution fallback**

At the top of `quality_check.py`, add:

```python
try:
    from scripts.handoff_parsing import (
        parse_frontmatter as _parse_handoff_frontmatter,
        parse_sections as _parse_handoff_sections,
        section_name as _section_name,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.handoff_parsing import (  # type: ignore[no-redef]
        parse_frontmatter as _parse_handoff_frontmatter,
        parse_sections as _parse_handoff_sections,
        section_name as _section_name,
    )
```

- [ ] **Step 5: Replace quality_check parsing wrappers**

Replace `parse_frontmatter` and `parse_sections` with compatibility wrappers:

```python
def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter fields as key-value pairs."""
    frontmatter, _ = _parse_handoff_frontmatter(content)
    return frontmatter


def parse_sections(content: str) -> list[dict[str, str]]:
    """Extract ## sections with current quality-check return shape."""
    _, body = _parse_handoff_frontmatter(content)
    return [
        {
            "heading": _section_name(section.heading),
            "content": section.content,
        }
        for section in _parse_handoff_sections(body)
    ]
```

- [ ] **Step 6: Run quality-check tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py -q
```

Expected: all quality-check tests pass. If existing tests assert the old no-frontmatter behavior, preserve the public wrapper return shape while still delegating fence tracking to `handoff_parsing.py`.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add \
  plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_handoff_parsing.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py
git commit -m "fix: share handoff section parsing"
```

---

### Task 5: Portable State Cleanup and Defer Atomic Writes

**Files:**
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/defer.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_defer.py`

- [ ] **Step 1: Replace hard-fail cleanup tests with fallback tests**

Replace existing hard-fail expectations instead of adding contradictory tests. In the live tree this includes `test_write_active_handoff_cleanup_failure_remains_recoverable`; if `test_active_writer_flow_cli_cleanup_failure_remains_recoverable` still asserts `result == 1`, `state cleanup failed`, or `cleanup_failed`, update it in the same step to expect successful fallback cleanup and committed state.

Use this direct-function test shape for the replacement:

```python
def test_write_active_handoff_falls_back_to_unlink_when_trash_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = session_state.write_resume_state(
        tmp_path / ".codex" / "handoffs" / ".session-state",
        "demo",
        str(tmp_path / "archive.md"),
    )
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="cleanup-fallback",
        created_at="2026-05-13T16:45:00Z",
    )
    content = "---\ntitle: Cleanup fallback\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    monkeypatch.setattr(active_writes._storage_primitives.subprocess, "run", fail_trash)

    result = active_writes.write_active_handoff(
        tmp_path,
        operation_state_path=reservation.operation_state_path,
        content=content,
        content_sha256=content_hash,
    )

    operation_state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert operation_state["state_cleanup_action"] == "cleared-primary-state"
    assert operation_state["state_cleanup_mechanism"] == "unlink"
    assert not state_path.exists()


def test_write_active_handoff_persists_cleanup_failed_when_both_mechanisms_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Critical invariant: when both `trash` and `unlink` fail, the existing
    # cleanup_failed recovery path at active_writes.py:565-584 must still fire
    # and persist cleanup_failed status to BOTH the operation-state file and
    # the transaction record. Without this, the new portable-cleanup primitive
    # would silently drop operator-actionable recovery state.
    state_path = session_state.write_resume_state(
        tmp_path / ".codex" / "handoffs" / ".session-state",
        "demo",
        str(tmp_path / "archive.md"),
    )
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="cleanup-both-fail",
        created_at="2026-05-13T16:45:00Z",
    )
    content = "---\ntitle: Cleanup both fail\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    original_unlink = Path.unlink

    def fail_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == state_path:
            raise PermissionError("unlink denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(active_writes._storage_primitives.subprocess, "run", fail_trash)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(active_writes.ActiveWriteError):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    operation_state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    assert operation_state["status"] == "cleanup_failed"
    assert operation_state["state_cleanup_action"] == "cleanup_failed"
    # Recovery from this state remains possible via recover_active_write_transaction
    # — that existing path is what proves cleanup_failed is operator-actionable, not a
    # bare traceback.
```

This test intentionally patches through a module import. Task 5 Step 5 must add `from scripts import storage_primitives as _storage_primitives` to `active_writes.py` and call `_storage_primitives.safe_delete(path)` rather than importing `safe_delete` directly.

- [ ] **Step 2: Replace session-state trash-failure tests with fallback tests**

Replace existing hard-fail expectations instead of adding contradictory tests. In the live tree this includes `test_clear_resume_state_warns_when_trash_fails` and `test_clear_state_cli_returns_1_when_trash_fails`; update both to expect unlink fallback success.

Use this direct-function test shape for the first replacement:

```python
def test_clear_resume_state_falls_back_to_unlink_when_trash_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir = tmp_path / ".session-state"
    state_path = session_state.write_resume_state(state_dir, "demo", str(tmp_path / "archive.md"))

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("trash")

    monkeypatch.setattr(session_state.storage_primitives.subprocess, "run", fail_trash)

    assert session_state.clear_resume_state(state_dir, str(state_path)) is True
    assert not state_path.exists()
```

For the CLI test, keep the existing `session_state.main([... "clear-state" ...])` shape but assert `exit_code == 0` and `not state_path.exists()`.

- [ ] **Step 3: Add defer atomic exclusive test**

Append to `test_defer.py`:

```python
def test_write_envelope_payload_uses_atomic_exclusive_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.defer as defer_module

    calls: list[tuple[Path, str]] = []

    def fake_write(path: Path, payload: str) -> Path:
        calls.append((path, payload))
        path.write_text(payload, encoding="utf-8")
        return path

    monkeypatch.setattr(defer_module, "write_text_atomic_exclusive", fake_write)

    written = defer_module._write_envelope_payload(tmp_path, "stem", '{"ok": true}')

    assert written == tmp_path / "stem.json"
    assert calls == [(tmp_path / "stem.json", '{"ok": true}')]
```

- [ ] **Step 4: Run focused tests and verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py::test_write_active_handoff_falls_back_to_unlink_when_trash_fails \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py::test_clear_resume_state_falls_back_to_unlink_when_trash_fails \
  plugins/turbo-mode/handoff/1.6.0/tests/test_defer.py::test_write_envelope_payload_uses_atomic_exclusive_writer -q
```

Expected: failures due to hard `trash` behavior and defer not calling the shared writer.

- [ ] **Step 5: Use safe_delete in active_writes**

Change the top-level import in `active_writes.py` to include the module object in both normal and fallback import paths:

```python
from scripts import storage_primitives as _storage_primitives
```

Keep existing selective imports for lock, hash, and JSON helpers if that preserves the smallest diff. Use the module import specifically for delete behavior so tests can patch `_storage_primitives.subprocess.run`.

Update `_clear_snapshotted_primary_state`:

```python
delete_result = _storage_primitives.safe_delete(path)
if delete_result.action not in {"deleted", "already_absent"}:
    raise ActiveWriteError(
        f"write-active-handoff failed: state cleanup failed via {delete_result.mechanism}. "
        f"Got: ({delete_result.error!r}, {str(path)!r:.100})"
    )
return "cleared-primary-state", str(path), delete_result.mechanism
```

Update call sites and persisted state to include:

```python
"state_cleanup_action": cleanup_action,
"state_cleanup_path": cleanup_path,
"state_cleanup_mechanism": cleanup_mechanism,
```

Update both call sites: `write_active_handoff` and `recover_active_write_transaction`. Both currently unpack `_clear_snapshotted_primary_state(state)` as a 2-tuple; both must unpack the new 3-tuple and persist `state_cleanup_mechanism` alongside the existing fields. Preserve existing `state_cleanup_action` values so older status checks remain stable.

- [ ] **Step 6: Use safe_delete in session_state**

Change the top-level import in `session_state.py` to include the module object in both normal and fallback import paths:

```python
from scripts import storage_primitives
```

Keep or update `write_json_atomic` references consistently; the required invariant for this task is that cleanup calls use `storage_primitives.safe_delete(path)` so tests can patch `session_state.storage_primitives.subprocess.run`.

Replace `_trash_path` with:

```python
def _delete_path(path: Path, *, context: str) -> bool:
    try:
        result = storage_primitives.safe_delete(path)
    except OSError as exc:
        print(
            f"state cleanup warning: {context} failed: {exc}. Got: {str(path)!r:.100}",
            file=sys.stderr,
        )
        return False
    if result.action in {"deleted", "already_absent"}:
        return True
    print(
        f"state cleanup warning: {context} failed. Got: {str(path)!r:.100}",
        file=sys.stderr,
    )
    return False
```

Replace `_trash_path` call sites with `_delete_path`.

- [ ] **Step 7: Use atomic exclusive text in defer**

Import `write_text_atomic_exclusive` in `defer.py` and replace `_write_envelope_payload` with:

```python
def _write_envelope_payload(envelopes_dir: Path, stem: str, payload: str) -> Path:
    """Write pre-serialized envelope payload to disk atomically."""
    return write_text_atomic_exclusive(envelopes_dir / f"{stem}.json", payload)
```

- [ ] **Step 8: Run touched tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_defer.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py -q
```

Expected: all touched tests pass.

- [ ] **Step 9: Commit Task 5**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/defer.py \
  plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_defer.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_storage_primitives.py
git commit -m "fix: make handoff state cleanup portable"
```

---

### Task 6: Consolidate Script Bootstrap Safely

**Files:**
- Create: `plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/defer.py`
- Modify: other `scripts/*.py` files with `except ModuleNotFoundError` fallback blocks after the four high-risk modules are green.
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_harness.py`
- Test: add bootstrap tests to `plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py`

- [ ] **Step 1: Add bootstrap test file**

Create `test_bootstrap.py`:

```python
from __future__ import annotations

import importlib
import subprocess
import sys
import types
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PLUGIN_ROOT / "scripts"
FAKE_PARENT_SCRIPTS = "/nonexistent/repo-root/scripts"


def test_bootstrap_keeps_plugin_scripts_first_under_shadowed_parent(
    monkeypatch,
) -> None:
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [FAKE_PARENT_SCRIPTS, str(SCRIPT_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    import scripts._bootstrap as bootstrap

    bootstrap.ensure_plugin_scripts_package()
    storage_authority = importlib.import_module("scripts.storage_authority")

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(storage_authority.__file__)
    assert FAKE_PARENT_SCRIPTS in list(scripts_pkg.__path__)  # type: ignore[attr-defined]


def test_bootstrap_is_idempotent_under_repeated_import(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))
    import scripts._bootstrap as bootstrap

    bootstrap.ensure_plugin_scripts_package()
    bootstrap.ensure_plugin_scripts_package()

    scripts_pkg = sys.modules["scripts"]
    paths = list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    assert paths.count(str(SCRIPT_DIR)) == 1
    assert paths[0] == str(SCRIPT_DIR)


def test_direct_script_execution_still_works() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "session_state.py"),
            "--help",
        ],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "usage:" in completed.stdout


def test_storage_authority_entrypoint_bootstraps_under_shadowed_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # Stage a fully adversarial fake parent `scripts` namespace: parent's
    # `_bootstrap.py` raises on import (proving plugin's `_bootstrap` ran),
    # parent's `storage_primitives.py` exposes booby-trapped functions
    # (proving plugin's `storage_primitives` ran). The test fails loudly if
    # the prelude resolves either submodule through the parent package.
    fake_parent = tmp_path / "parent_scripts"
    fake_parent.mkdir()
    (fake_parent / "_bootstrap.py").write_text(
        "raise AssertionError('wrong _bootstrap loaded from shadowed parent')\n",
        encoding="utf-8",
    )
    (fake_parent / "storage_primitives.py").write_text(
        "def write_json_atomic(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n"
        "def sha256_regular_file_or_none(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n"
        "def read_json_object(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n",
        encoding="utf-8",
    )
    for module_name in (
        "scripts._bootstrap",
        "scripts.storage_authority",
        "scripts.storage_primitives",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent), str(SCRIPT_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    storage_authority = importlib.import_module("scripts.storage_authority")

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(fake_parent) in list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(storage_authority.__file__)
    assert str(SCRIPT_DIR) in str(sys.modules["scripts.storage_primitives"].__file__)
    assert str(SCRIPT_DIR) in str(sys.modules["scripts._bootstrap"].__file__)
```

- [ ] **Step 2: Run bootstrap tests and verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py -q
```

Expected: file missing or `_bootstrap` import failures.

- [ ] **Step 3: Create `_bootstrap.py`**

Create `scripts/_bootstrap.py`:

```python
"""Import bootstrap for direct Handoff script execution."""

from __future__ import annotations

import sys
import types
from pathlib import Path


def plugin_script_dir() -> Path:
    """Return this plugin's script directory."""
    return Path(__file__).resolve().parent


def plugin_root() -> Path:
    """Return this plugin root."""
    return plugin_script_dir().parent


def ensure_plugin_scripts_package() -> None:
    """Ensure imports from scripts.* resolve to this plugin's scripts directory first."""
    script_dir = str(plugin_script_dir())
    plugin_parent = str(plugin_root())
    if plugin_parent not in sys.path:
        sys.path.insert(0, plugin_parent)
    scripts_pkg = sys.modules.get("scripts")
    if scripts_pkg is None or not hasattr(scripts_pkg, "__path__"):
        scripts_pkg = types.ModuleType("scripts")
        scripts_pkg.__path__ = [script_dir]  # type: ignore[attr-defined]
        sys.modules["scripts"] = scripts_pkg
        return
    package_path = list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    package_path = [entry for entry in package_path if entry != script_dir]
    package_path.insert(0, script_dir)
    scripts_pkg.__path__ = package_path  # type: ignore[attr-defined]


ensure_plugin_scripts_package()
```

- [ ] **Step 4: Replace the first high-risk bootstrap block**

In `storage_authority.py`, replace the heavyweight `except ModuleNotFoundError` package synthesis block with a path-based bootstrap prelude before any `from scripts.*` imports:

```python
def _load_bootstrap_by_path() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    bootstrap_path = Path(__file__).resolve().parent / "_bootstrap.py"
    if "scripts._bootstrap" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location("scripts._bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            "handoff bootstrap failed: missing or unloadable _bootstrap.py. "
            f"Got: {str(bootstrap_path)!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)


_load_bootstrap_by_path()
del _load_bootstrap_by_path

from scripts.storage_primitives import (
    read_json_object as _read_json_object_primitive,
    sha256_regular_file_or_none as _content_sha256,
    write_json_atomic as _write_json_atomic,
)
```

`_bootstrap` is loaded by absolute filesystem path rather than via `from scripts import _bootstrap`. This is the load-bearing defense against shadowing: a preloaded parent `scripts` package may carry its own `_bootstrap.py`, which `from scripts import _bootstrap` would resolve to first. Path-based loading skips package resolution entirely, guarantees this plugin's `_bootstrap.py` runs `ensure_plugin_scripts_package()` before any `from scripts.storage_primitives import ...` is attempted, and registers the loaded module as `scripts._bootstrap` in `sys.modules` so any later `from scripts import _bootstrap` is a no-op. Keep the current `TYPE_CHECKING` import unchanged.

- [ ] **Step 5: Replace active_writes and load_transactions bootstrap blocks**

Apply the same path-based bootstrap prelude from Step 4 in `active_writes.py` and `load_transactions.py`. Keep the imported public names exactly as they are today; only replace the package-synthesis logic.

- [ ] **Step 6: Replace simpler fallback blocks**

For simple direct-execution fallback blocks, use the same path-based prelude before the real imports:

```python
def _load_bootstrap_by_path() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    bootstrap_path = Path(__file__).resolve().parent / "_bootstrap.py"
    if "scripts._bootstrap" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location("scripts._bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            "handoff bootstrap failed: missing or unloadable _bootstrap.py. "
            f"Got: {str(bootstrap_path)!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)


_load_bootstrap_by_path()
del _load_bootstrap_by_path

from scripts.some_module import some_name
```

Apply only to files with existing fallback blocks. Do not add bootstrap imports to modules that have no local `scripts.*` imports.

- [ ] **Step 7: Run bootstrap tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py -q
```

Expected: all bootstrap tests pass.

- [ ] **Step 8: Run installed-host and direct-execution probes**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider \
  plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_harness.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py -q
```

Expected: installed-host harness and skill-doc execution contracts still pass.

- [ ] **Step 9: Run import smoke probes**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run python -c "import subprocess, sys; subprocess.run([sys.executable, '-c', 'from scripts.active_writes import begin_active_write; from scripts.load_transactions import load_handoff; from scripts.storage_authority import discover_handoff_inventory'], cwd='plugins/turbo-mode/handoff/1.6.0', check=True)"
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run python -c "import runpy; runpy.run_path('plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py'); runpy.run_path('plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py'); runpy.run_path('plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py')"
```

Expected: both commands exit 0.

- [ ] **Step 10: Run all Handoff tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected: all Handoff plugin tests pass.

- [ ] **Step 11: Commit Task 6**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts plugins/turbo-mode/handoff/1.6.0/tests
git commit -m "chore: consolidate handoff script bootstrap"
```

---

## Final Verification

After all selected tasks are complete, run:

```bash
git status --short
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache-handoff-repair uv run pytest -p no:cacheprovider plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected:

- `git status --short` shows only intentional changes before final commit, and clean after commits.
- Full Handoff test suite passes.
- No `__pycache__` directories are created under `plugins/turbo-mode/handoff/1.6.0/scripts`.

If bytecode residue appears, use `trash` for the residue only after verifying it is untracked and unrelated to durable handoff artifacts:

```bash
git status --short --ignored plugins/turbo-mode/handoff/1.6.0/scripts
trash plugins/turbo-mode/handoff/1.6.0/scripts/__pycache__
```

## Self-Review Checklist

- C1 is covered by Task 1 and Task 2.
- C2 is covered by Task 3 marker degradation.
- C3 is covered by Task 4 parser consolidation.
- C4 is covered by Task 1 atomic exclusive text and Task 5 defer integration.
- E6 is covered by Task 3 consumed-registry degradation.
- H3 is covered by Task 1 `safe_delete` and Task 5 cleanup integration.
- Bootstrap structural debt is covered last in Task 6 with unconditional prelude, shadowing, containment, and idempotency tests.
- The Task 6 shadowing test includes a fake parent `scripts.storage_primitives` so the test fails if the real entry-point import path does not invoke `_bootstrap` before importing `scripts.storage_primitives`.
- Performance work is intentionally excluded and should get a separate plan.

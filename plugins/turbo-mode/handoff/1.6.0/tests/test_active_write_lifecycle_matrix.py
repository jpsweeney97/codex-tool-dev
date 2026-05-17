"""Write-spy lifecycle-matrix gate for the active-write status-domain partition.

Spies the shared atomic-write chokepoint
(storage_primitives.write_json_atomic) and asserts the discriminating
invariant on EVERY status write (transients included), for every reachable
lifecycle path. This is the runtime enforcement of the partition (the
Literal aliases have no teeth under the repo's ruff+pytest gate).

Tripwire (Stop Condition 1): if any write puts 'completed' or 'unreadable'
into a .../active-writes/ path, or 'committed'/'begun'/'unreadable' into a
.../transactions/ path, the source-domain model is falsified -- STOP.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import get_args

import pytest
import turbo_mode_handoff_runtime.active_writes as active_writes
import turbo_mode_handoff_runtime.chain_state as chain_state
import turbo_mode_handoff_runtime.storage_primitives as storage_primitives

OP_MEMBERS = set(get_args(active_writes.ActiveWriteOperationStateStatus))
TX_MEMBERS = set(get_args(active_writes.ActiveWriteTransactionStatus))
CREATED_AT = "2026-05-13T16:45:00Z"

# Runtime-reachable members. Every member EXCEPT operation-state
# 'unreadable' is produced by some scenario below. 'unreadable' is the
# synthetic unreadable-record marker built by
# active_writes._unreadable_active_write_record; it is never emitted by a
# normal lifecycle or recovery flow, so it is intentionally
# static-pin-only (Task 1) and excluded here (Gate G3 rationale).
RUNTIME_OP_MEMBERS = OP_MEMBERS - {"unreadable"}
RUNTIME_TX_MEMBERS = set(TX_MEMBERS)


class WriteSpy:
    """Records (domain, status) for every status-bearing atomic write and
    delegates to the real writer so behavior is unchanged."""

    def __init__(self) -> None:
        self._real = storage_primitives.write_json_atomic
        self.events: list[tuple[str, object]] = []

    def __call__(self, path: Path, payload: dict[str, object]) -> None:
        parts = Path(path).parts
        if "transactions" in parts:
            domain = "tx"
        elif "active-writes" in parts:
            domain = "op"
        else:
            if "status" not in payload:
                self._real(path, payload)
                return
            domain = "other"
        self.events.append((domain, payload.get("status")))
        self._real(path, payload)

    def statuses(self) -> set[object]:
        return {status for _, status in self.events}

    def observed_by_domain(self) -> dict[str, set[object]]:
        """Statuses observed, bucketed by the file domain they were
        written to. The coverage gate (review Finding 2) must check op
        members against op-domain writes and tx members against tx-domain
        writes -- a domain-blind union lets a shared status seen in only
        one domain mask a per-domain regression in the other."""
        by_domain: dict[str, set[object]] = {"op": set(), "tx": set()}
        for domain, status in self.events:
            if domain in by_domain:
                by_domain[domain].add(status)
        return by_domain

    def assert_partitioned(self, scenario: str) -> None:
        for domain, status in self.events:
            if domain == "op":
                assert status in OP_MEMBERS, (
                    f"{scenario}: op write status {status!r} not in op alias"
                )
                # 'completed' is tx-only; 'unreadable' is synthetic and must
                # never be persisted to ANY domain (Round-4 finding F5 -- the
                # op arm was previously missing, so unreadable-into-op was
                # only caught by the coverage test's tail assertion, not the
                # per-scenario tripwire). 'unreadable' is in OP_MEMBERS so the
                # membership assert above does not catch it.
                assert status not in {"completed", "unreadable"}, (
                    f"{scenario}: TRIPWIRE {status!r} written to operation-state file"
                )
            elif domain == "tx":
                assert status in TX_MEMBERS, (
                    f"{scenario}: tx write status {status!r} not in tx alias"
                )
                assert status not in {"committed", "begun", "unreadable"}, (
                    f"{scenario}: TRIPWIRE {status!r} written to transaction file"
                )
            else:
                pytest.fail(
                    f"{scenario}: status {status!r} written to an unclassified "
                    "atomic-write path"
                )


def _install_spy(monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = WriteSpy()
    monkeypatch.setattr(storage_primitives, "write_json_atomic", spy)
    return spy


def _begin(tmp_path: Path, *, slug: str, lease_seconds: int = 1800):
    return active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug=slug,
        created_at=CREATED_AT,
        lease_seconds=lease_seconds,
    )


def _read(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_write_spy_intercepts_chain_state_importer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_state_path = tmp_path / "docs" / "handoffs" / ".session-state" / "handoff-demo"
    legacy_state_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_state_path.write_text(
        str(tmp_path / ".codex" / "handoffs" / "archive" / "old.md"),
        encoding="utf-8",
    )
    legacy_hash = hashlib.sha256(legacy_state_path.read_bytes()).hexdigest()

    spy = _install_spy(monkeypatch)
    continued = chain_state.continue_chain_state(
        tmp_path,
        project_name="demo",
        state_path=legacy_state_path.relative_to(tmp_path).as_posix(),
        expected_payload_sha256=legacy_hash,
    )

    assert continued["status"] == "continued"
    assert ("tx", "completed") in spy.events
    spy.assert_partitioned("continue-chain-state")


# --- scenario drivers (each returns its WriteSpy) -----------------------


def _drive_begin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="begin")
    assert _read(res.operation_state_path)["status"] == "begun"
    assert _read(res.transaction_path)["status"] == "pending_before_write"
    return spy


def _drive_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="success")
    content = "body"
    active_writes.write_active_handoff(
        tmp_path,
        operation_state_path=res.operation_state_path,
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
    assert _read(res.operation_state_path)["status"] == "committed"
    assert _read(res.transaction_path)["status"] == "completed"
    # The transient window (content-generated -> write-pending) MUST have
    # been written on both domains and MUST satisfy the partition.
    assert "content-generated" in spy.statuses()
    assert "write-pending" in spy.statuses()
    return spy


def _drive_abandon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="abandon")
    active_writes.abandon_active_write(
        tmp_path,
        operation_state_path=res.operation_state_path,
        reason="test",
    )
    assert _read(res.operation_state_path)["status"] == "abandoned"
    assert _read(res.transaction_path)["status"] == "abandoned"
    return spy


def _drive_reservation_expired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_rejects_expired_reservation_before_output_write
    # Deterministic expiry trigger: a hard past lease_expires_at, NOT a
    # lease_seconds=0 + wall-clock race (Round-4 finding F4). datetime.now is
    # non-monotonic; an NTP step-back between begin and the freshness check
    # must not un-expire a regression-gate scenario. The hand-edit is a plain
    # write_text (NOT write_json_atomic) so the spy does not record the
    # setup mutation -- only the begin writes and the reservation_expired
    # write-path writes are spied.
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="expired")
    state = _read(res.operation_state_path)
    state["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="reservation expired"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    assert _read(res.operation_state_path)["status"] == "reservation_expired"
    assert _read(res.transaction_path)["status"] == "reservation_expired"
    return spy


def _drive_content_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="mismatch")
    res.allocated_active_path.parent.mkdir(parents=True, exist_ok=True)
    res.allocated_active_path.write_text("OTHER CONTENT", encoding="utf-8")
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="content mismatch"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    # Write-path mismatch (the write_active_handoff content-mismatch
    # branch) persists ONLY the operation-state record; the transaction
    # stays at its last value, content-generated, from the prior
    # _persist_operation_and_transaction call.
    assert _read(res.operation_state_path)["status"] == "content_mismatch"
    assert _read(res.transaction_path)["status"] == "content-generated"
    return spy


def _drive_conflict_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_rejects_changed_state_snapshot_before_output_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="state-conflict")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    conflicting_state = state_dir / "handoff-demo-conflict.json"
    conflicting_state.write_text(
        json.dumps(
            {
                "state_path": str(conflicting_state),
                "project": "demo",
                "resume_token": "conflict",
                "archive_path": "/tmp/other.md",
                "created_at": "2026-05-13T16:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    content = "body"
    with pytest.raises(active_writes.ActiveWriteError, match="state snapshot changed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    updated = _read(res.operation_state_path)
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "state_snapshot_changed"
    assert _read(res.transaction_path)["status"] == "reservation_conflict"
    return spy


def _drive_conflict_watermark(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_rejects_changed_transaction_watermark_before_output_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="transaction-conflict")
    conflict_transaction = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "transactions"
        / "external-conflict.json"
    )
    conflict_transaction.write_text(
        json.dumps(
            {
                "transaction_id": "external-conflict",
                "operation": "load",
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )
    content = "body"
    with pytest.raises(
        active_writes.ActiveWriteError, match="transaction watermark changed"
    ):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )
    updated = _read(res.operation_state_path)
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "transaction_watermark_changed"
    assert _read(res.transaction_path)["status"] == "reservation_conflict"
    return spy


def _drive_cleanup_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_write_active_handoff_persists_cleanup_failed_when_both_mechanisms_fail
    # Drives the REAL cleanup branch (write_active_handoff via
    # _clear_snapshotted_primary_state -> _storage_primitives.safe_delete)
    # by failing BOTH delete mechanisms -- it does NOT monkeypatch the
    # cleanup helper itself, so the genuine persistence path runs (review
    # Finding 4: prefer the copied real setup over synthetic injection).
    spy = _install_spy(monkeypatch)
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "previous.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-resume.json"
    state_path.write_text(
        json.dumps(
            {
                "state_path": str(state_path),
                "project": "demo",
                "resume_token": "resume",
                "archive_path": str(archive),
                "created_at": "2026-05-13T16:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    res = _begin(tmp_path, slug="cleanup-both-fail")
    content = "body"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    original_subprocess_run = active_writes._storage_primitives.subprocess.run

    def fail_trash(*args: object, **kwargs: object) -> object:
        if not args or not isinstance(args[0], list) or args[0][:1] != ["trash"]:
            return original_subprocess_run(*args, **kwargs)
        raise FileNotFoundError("trash")

    original_unlink = Path.unlink

    def fail_unlink(self: Path, *a: object, **k: object) -> None:
        if self.resolve() == state_path.resolve():
            raise PermissionError("unlink denied")
        return original_unlink(self, *a, **k)

    monkeypatch.setattr(
        active_writes._storage_primitives.subprocess, "run", fail_trash
    )
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(active_writes.ActiveWriteError, match="state cleanup failed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=res.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )
    assert _read(res.operation_state_path)["status"] == "cleanup_failed"
    assert _read(res.transaction_path)["status"] == "cleanup_failed"
    return spy


def _drive_recover_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_active_write_transaction_recover_records_pending_before_write
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-pending")
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = hashlib.sha256(b"missing output").hexdigest()
    state["output_sha256"] = state["content_hash"]
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=res.operation_state_path,
    )
    assert recovered["status"] == "pending_before_write"
    assert _read(res.transaction_path)["status"] == "pending_before_write"
    return spy


def _drive_recover_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_active_write_transaction_recover_records_content_mismatch
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-mismatch")
    expected = "---\ntitle: Expected\n---\n\n# Expected\n"
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    res.allocated_active_path.write_text(
        "---\ntitle: Different\n---\n\n# Different\n", encoding="utf-8"
    )
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = expected_hash
    state["output_sha256"] = expected_hash
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    with pytest.raises(active_writes.ActiveWriteError, match="content mismatch"):
        active_writes.recover_active_write_transaction(
            tmp_path,
            operation_state_path=res.operation_state_path,
        )
    assert _read(res.operation_state_path)["status"] == "content_mismatch"
    assert _read(res.transaction_path)["status"] == "content_mismatch"
    return spy


def _drive_recover_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Direct-API EQUIVALENT (NOT a verbatim copy -- Round-4 F1) of:
    # test_active_writes.py::
    # test_active_write_transaction_recover_commits_verified_written_output
    # That named test is a subprocess/CLI test; this driver is the
    # behavior-verified direct-API form, matching the other drivers. The
    # equivalence (written_not_confirmed -> op 'committed' / tx 'completed'
    # via recover_active_write_transaction, no snapshot paths) was traced
    # against live source.
    # This is the ONLY driver that exercises the recovery-success write
    # site -- the single most dangerous site to leave unguarded because it
    # writes BOTH discriminating terminals. Its absence was the blocking
    # round-2 finding; the plan's own vocabulary table had admitted
    # "recover happy not driven".
    spy = _install_spy(monkeypatch)
    res = _begin(tmp_path, slug="recover-success")
    content = "---\ntitle: Recover\n---\n\n# Written\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    res.allocated_active_path.write_text(content, encoding="utf-8")
    state = _read(res.operation_state_path)
    state["status"] = "written_not_confirmed"
    state["content_hash"] = content_hash
    state["output_sha256"] = content_hash
    res.operation_state_path.write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=res.operation_state_path,
    )
    assert recovered["status"] == "committed"
    assert _read(res.operation_state_path)["status"] == "committed"
    assert _read(res.transaction_path)["status"] == "completed"
    return spy


def _drive_auto_expire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSpy:
    # Copied setup: test_active_writes.py::
    # test_begin_active_write_auto_expires_stale_pre_output_reservation
    # This is the ONLY driver that exercises the begin-time auto-expire
    # write site (active_writes._auto_expire_pre_output_reservation, which
    # writes both the op and tx records) -- distinct from the write-path
    # expiry that _drive_reservation_expired covers. A second compatible
    # begin auto-expires the stale pre-output reservation.
    spy = _install_spy(monkeypatch)
    first = _begin(tmp_path, slug="auto-expire", lease_seconds=-1)
    active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="auto-expire-replacement",
        created_at="2026-05-13T16:46:00Z",
    )
    assert _read(first.operation_state_path)["status"] == "reservation_expired"
    assert _read(first.transaction_path)["status"] == "reservation_expired"
    return spy


ALL_DRIVERS = (
    _drive_begin,
    _drive_success,
    _drive_abandon,
    _drive_reservation_expired,
    _drive_auto_expire,
    _drive_content_mismatch,
    _drive_conflict_snapshot,
    _drive_conflict_watermark,
    _drive_cleanup_failed,
    _drive_recover_pending,
    _drive_recover_mismatch,
    _drive_recover_success,
)


@pytest.mark.parametrize("driver", ALL_DRIVERS, ids=lambda d: d.__name__)
def test_scenario_partition_holds_for_every_write(
    driver, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = driver(tmp_path, monkeypatch)
    assert spy.events, f"{driver.__name__}: spy captured no writes"
    spy.assert_partitioned(driver.__name__)


def test_observed_status_coverage(tmp_path: Path) -> None:
    """Gate G3 / Stop Condition 3: every runtime-reachable alias member
    must be observed BY ITS OWN DOMAIN -- an operation-state member in an
    operation-state (.../active-writes/) write, a transaction member in a
    transaction (.../transactions/) write. A domain-blind union (the prior
    implementation) let a shared status observed in only one domain mask a
    per-domain regression in the other (review Finding 2). Each driver runs
    in its OWN MonkeyPatch context so a fault-injection patch (e.g.
    _drive_cleanup_failed's subprocess/Path.unlink overrides) cannot leak
    into a later driver and silently corrupt coverage. 'unreadable' is the
    only deliberately-excluded member (synthetic record, never written via
    the atomic-write chokepoint by any lifecycle flow)."""
    observed: dict[str, set[object]] = {"op": set(), "tx": set()}
    for index, driver in enumerate(ALL_DRIVERS):
        scenario_dir = tmp_path / f"s{index}"
        scenario_dir.mkdir()
        with pytest.MonkeyPatch.context() as mp:
            spy = driver(scenario_dir, mp)
            assert spy.events, f"{driver.__name__}: zero events"
            spy.assert_partitioned(driver.__name__)
            for domain, statuses in spy.observed_by_domain().items():
                observed[domain] |= statuses
    missing_op = RUNTIME_OP_MEMBERS - observed["op"]
    missing_tx = RUNTIME_TX_MEMBERS - observed["tx"]
    assert not missing_op, (
        f"operation-state members never observed in an operation-state "
        f"write: {missing_op}"
    )
    assert not missing_tx, (
        f"transaction members never observed in a transaction write: "
        f"{missing_tx}"
    )
    assert "unreadable" not in (observed["op"] | observed["tx"]), (
        "'unreadable' was observed in a lifecycle write — the vocabulary "
        "model's static-pin-only assumption is wrong; revisit Gate G3."
    )

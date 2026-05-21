from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import scripts.ticket_doctor as ticket_doctor_script
import scripts.ticket_payloads as ticket_payloads
import scripts.ticket_runtime_readiness as ticket_runtime_readiness
from scripts.ticket_triage import (
    DoctorInputError,
    _source_cache_report,
    _tree_manifest,
    ticket_doctor,
)

DOCTOR_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ticket_doctor.py"


def _manifest_guard_command(plugin_root: Path) -> str:
    manifest = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    return manifest["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


def test_ticket_doctor_reports_project_and_plugin_paths(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["project"]["tickets_dir"] == str(tmp_tickets)
    assert report["plugin"]["plugin_root"] == str(plugin_root)
    assert report["plugin"]["cache_root"] == str(plugin_root)
    assert report["plugin"]["source_cache_equal"] is True
    assert report["runtime"]["live_hook_probe"] == "not_run"
    assert report["runtime_proof"]["status"] == "missing"


def test_ticket_doctor_reports_invalid_runtime_proof_status(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    proof_path = tmp_tickets.parent.parent / ".codex" / "ticket-runtime-proof.json"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text("{not json", encoding="utf-8")

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["runtime_proof"]["exists"] is True
    assert report["runtime_proof"]["status"] == "invalid"
    assert "Expecting property name" in report["runtime_proof"]["error"]


def test_ticket_doctor_reports_activated_runtime_proof_status(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    proof_path = tmp_tickets.parent.parent / ".codex" / "ticket-runtime-proof.json"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text(
        json.dumps(
            {
                "status": "activated",
                "schema_version": "installed_ticket_runtime_readiness-v1",
                "expires_at": "2026-05-21T23:59:59Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["runtime_proof"]["exists"] is True
    assert report["runtime_proof"]["status"] == "activated"
    assert report["runtime_proof"]["schema_version"] == "installed_ticket_runtime_readiness-v1"


def test_ticket_doctor_reports_stale_runtime_proof_status(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    proof_path = tmp_tickets.parent.parent / ".codex" / "ticket-runtime-proof.json"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text(
        json.dumps(
            {
                "status": "activated",
                "schema_version": "installed_ticket_runtime_readiness-v1",
                "expires_at": "2026-05-19T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["runtime_proof"]["status"] == "stale"
    assert report["runtime_proof"]["raw_status"] == "activated"
    assert report["runtime_proof"]["error_code"] == "stale_proof"


def test_ticket_doctor_reports_naive_runtime_proof_expiry_as_invalid(
    tmp_tickets: Path,
) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    proof_path = tmp_tickets.parent.parent / ".codex" / "ticket-runtime-proof.json"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text(
        json.dumps(
            {
                "status": "activated",
                "schema_version": "installed_ticket_runtime_readiness-v1",
                "expires_at": "2026-05-21T23:59:59",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["runtime_proof"]["status"] == "invalid"
    assert report["runtime_proof"]["raw_status"] == "activated"
    assert report["runtime_proof"]["error_code"] == "proof_invalid"
    assert "expires_at" in report["runtime_proof"]["error"]


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


def test_activate_runtime_returns_ok_with_activated_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: ticket_runtime_readiness.ActivationSuccess(
            proof={
                "status": "activated",
                "activation_scope": {"gated_execute_surfaces": ["direct_execute"]},
            },
            message="final proof activated",
        ),
        raising=False,
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "build_activation_candidate",
        lambda **_kwargs: ticket_runtime_readiness.ActivationSuccess(
            proof={
                "status": "activated",
                "activation_scope": {"gated_execute_surfaces": ["direct_execute"]},
            },
            message="final proof activated",
        ),
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 0
    assert response["state"] == "ok"
    assert "error_code" not in response
    assert response["data"]["mode"] == "activate-runtime"
    assert response["data"]["proof"]["status"] == "activated"


def test_activate_runtime_propagates_host_policy_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code="host_policy_blocked",
        message="contained workspaceWrite turn failed",
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "build_activation_candidate",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "host_policy_blocked"


def test_activate_runtime_propagates_deterministic_driver_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code="deterministic_driver_unavailable",
        message="app-server transcript did not capture the command turn",
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "build_activation_candidate",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "deterministic_driver_unavailable"


def test_activate_runtime_preserves_late_publication_failure_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code="deterministic_driver_unavailable",
        message=(
            "Direct execute smoke already succeeded, but final runtime proof publication "
            "failed: final proof denied. Run evidence remains under "
            ".codex/ticket-runtime-smoke/run-1"
        ),
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "build_activation_candidate",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "deterministic_driver_unavailable"
    assert response["message"] == blocked_result.message


def test_activate_runtime_propagates_hook_contract_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code="hook_contract_blocked",
        message="installed hook still emits unsupported output",
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "build_activation_candidate",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "hook_contract_blocked"


@pytest.mark.parametrize(
    ("error_code", "expected_summary"),
    [
        ("proof_invalid", "The Ticket runtime proof is invalid or incomplete."),
        ("stale_proof", "The Ticket runtime proof has expired."),
    ],
)
def test_activate_runtime_has_clean_proof_recovery_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
    expected_summary: str,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code=error_code,
        message="runtime proof needs activation",
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == error_code
    assert "internal:" not in response["message"]
    assert response["data"]["recovery_hint"]["code"] == error_code
    assert response["data"]["recovery_hint"]["summary"] == expected_summary


def test_activate_runtime_surfaces_unknown_recovery_hint_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    marketplace_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    blocked_result = ticket_runtime_readiness.ActivationFailure(
        error_code="new_unregistered_code",
        message="unregistered runtime failure",
    )
    monkeypatch.setattr(
        ticket_doctor_script,
        "activate_runtime",
        lambda **_kwargs: blocked_result,
        raising=False,
    )

    response, exit_code = ticket_doctor_script.activate_runtime_payload(
        project_root=tmp_path,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert exit_code == 1
    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "new_unregistered_code"
    assert response["message"] == "unregistered runtime failure"
    assert response["data"]["recovery_hint_error"] == (
        "unknown recovery hint code: 'new_unregistered_code'"
    )
    assert response["data"]["recovery_hint"]["code"] == "runtime_readiness_required"


def test_activate_runtime_cli_parser_reaches_structured_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    outside_tickets_dir = tmp_path.parent / f"{tmp_path.name}-outside" / "tickets"
    marketplace_path = tmp_path / "missing-marketplace.json"
    monkeypatch.chdir(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(DOCTOR_SCRIPT),
            "activate-runtime",
            str(outside_tickets_dir),
            "--marketplace-path",
            str(marketplace_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    response = json.loads(completed.stdout)
    assert response["state"] == "policy_blocked"
    assert "usage:" not in completed.stdout
    assert "tickets_dir" in response["message"]


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


def test_stale_payloads_uses_strict_ttl_boundary(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    now = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    stale_after = timedelta(hours=24)

    just_under = payload_dir / "just-under.json"
    exact = payload_dir / "exact.json"
    just_over = payload_dir / "just-over.json"
    old_text = payload_dir / "old.txt"
    for path in [just_under, exact, just_over, old_text]:
        path.write_text("{}", encoding="utf-8")
    os.utime(just_under, (now.timestamp() - stale_after.total_seconds() + 1,) * 2)
    os.utime(exact, (now.timestamp() - stale_after.total_seconds(),) * 2)
    os.utime(just_over, (now.timestamp() - stale_after.total_seconds() - 1,) * 2)
    os.utime(old_text, (now.timestamp() - stale_after.total_seconds() - 1,) * 2)

    stale = ticket_payloads.stale_payloads(
        tmp_path,
        now=now,
        stale_after=stale_after,
    )

    assert [item.path for item in stale] == [just_over]
    assert old_text.exists()


def test_clean_stale_payloads_deletes_only_json_older_than_ttl(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    now = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    stale_after = timedelta(hours=24)

    just_under = payload_dir / "just-under.json"
    exact = payload_dir / "exact.json"
    just_over = payload_dir / "just-over.json"
    old_text = payload_dir / "old.txt"
    for path in [just_under, exact, just_over, old_text]:
        path.write_text("{}", encoding="utf-8")
    os.utime(just_under, (now.timestamp() - stale_after.total_seconds() + 1,) * 2)
    os.utime(exact, (now.timestamp() - stale_after.total_seconds(),) * 2)
    os.utime(just_over, (now.timestamp() - stale_after.total_seconds() - 1,) * 2)
    os.utime(old_text, (now.timestamp() - stale_after.total_seconds() - 1,) * 2)

    deleted = ticket_payloads.clean_stale_payloads(
        tmp_path,
        now=now,
        stale_after=stale_after,
    )

    assert [item.path for item in deleted] == [just_over]
    assert just_under.exists()
    assert exact.exists()
    assert not just_over.exists()
    assert old_text.exists()


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
    response = json.loads(completed.stdout)
    assert "containment failed" in response["message"]


def test_ticket_doctor_clean_stale_payloads_rejects_in_project_tmp_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    payload = tickets_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "ticket-tmp").symlink_to(tickets_dir, target_is_directory=True)
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

    assert completed.returncode != 0
    assert payload.exists()
    assert response["state"] == "policy_blocked"
    assert "must not be a symlink" in response["message"]


def test_ticket_doctor_clean_stale_payloads_rejects_codex_parent_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    external_codex = tmp_path.parent / f"{tmp_path.name}-external-codex"
    external_payload_dir = external_codex / "ticket-tmp"
    external_payload_dir.mkdir(parents=True)
    payload = external_payload_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    (tmp_path / ".codex").symlink_to(external_codex, target_is_directory=True)
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

    assert completed.returncode != 0
    assert payload.exists()
    assert response["state"] == "policy_blocked"
    assert "symlink" in response["message"]


def test_ticket_doctor_clean_stale_payloads_rejects_symlink_payload_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    payload = payload_dir / "old.json"
    payload.symlink_to(target)
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time), follow_symlinks=False)
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

    assert completed.returncode != 0
    assert target.exists()
    assert payload.is_symlink()
    assert response["state"] == "policy_blocked"
    assert "symlink" in response["message"]


def test_clean_stale_payloads_deletes_from_opened_dir_when_tmp_swapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    payload = payload_dir / "old.json"
    payload.write_text("{}", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(payload, (old_time, old_time))
    original_payload_dir = tmp_path / ".codex" / "ticket-tmp-original"
    replacement_payload = payload_dir / "old.json"
    original_unlink = ticket_payloads.os.unlink
    swapped = False

    def unlink_after_swap(path: str, *, dir_fd: int | None = None) -> None:
        nonlocal swapped, replacement_payload
        if not swapped:
            swapped = True
            payload_dir.rename(original_payload_dir)
            payload_dir.mkdir()
            replacement_payload = payload_dir / "old.json"
            replacement_payload.write_text("replacement", encoding="utf-8")
        original_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(ticket_payloads.os, "unlink", unlink_after_swap)

    deleted = ticket_payloads.clean_stale_payloads(tmp_path)

    assert swapped
    assert len(deleted) == 1
    assert not (original_payload_dir / "old.json").exists()
    assert replacement_payload.exists()


def test_delete_consumed_payload_deletes_from_opened_dir_when_tmp_swapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".git").mkdir()
    payload_dir = tmp_path / ".codex" / "ticket-tmp"
    payload_dir.mkdir(parents=True)
    payload = payload_dir / "capture.json"
    payload.write_text("{}", encoding="utf-8")
    original_payload_dir = tmp_path / ".codex" / "ticket-tmp-original"
    replacement_payload = payload_dir / "capture.json"
    original_unlink = ticket_payloads.os.unlink
    swapped = False

    def unlink_after_swap(path: str, *, dir_fd: int | None = None) -> None:
        nonlocal swapped, replacement_payload
        if not swapped:
            swapped = True
            payload_dir.rename(original_payload_dir)
            payload_dir.mkdir()
            replacement_payload = payload_dir / "capture.json"
            replacement_payload.write_text("replacement", encoding="utf-8")
        original_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(ticket_payloads.os, "unlink", unlink_after_swap)

    deleted = ticket_payloads.delete_consumed_payload(payload, tmp_path)

    assert swapped
    assert deleted is True
    assert not (original_payload_dir / "capture.json").exists()
    assert replacement_payload.exists()


def test_source_cache_report_reports_missing_cache(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    missing_cache = tmp_path / "missing-cache"

    report = _source_cache_report(plugin_root, missing_cache)

    assert report["cache_exists"] is False
    assert report["source_cache_equal"] is False


def test_ticket_doctor_detects_same_size_content_divergence(
    tmp_tickets: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "same.py").write_text("alpha\n", encoding="utf-8")
    (cache / "same.py").write_text("bravo\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["same.py"]


def test_ticket_doctor_source_cache_equal_is_exact_not_filtered(
    tmp_tickets: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / ".audit").mkdir()
    (source / ".audit" / "source-only.jsonl").write_text("audit\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == [".audit/source-only.jsonl"]


def test_ticket_doctor_source_cache_equal_detects_empty_directory_difference(
    tmp_tickets: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "empty-source-only").mkdir()

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["empty-source-only"]


def test_ticket_doctor_source_cache_equal_detects_file_kind_difference(
    tmp_tickets: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "kind").mkdir()
    (cache / "kind").write_text("kind\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["kind"]


def test_ticket_doctor_reports_generated_residue_separately(
    tmp_tickets: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["generated_residue"] == [
        "source:.pytest_cache",
        "source:.pytest_cache/README.md",
    ]


def test_ticket_doctor_classifies_live_hook_probe_output(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    guard_command = _manifest_guard_command(plugin_root)
    probe_output = tmp_path / "hook-probe.out"
    probe_output.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": 1,
                        "result": {
                            "plugin": {
                                "summary": {
                                    "id": "ticket@turbo-mode",
                                    "enabled": True,
                                    "installed": True,
                                },
                                "marketplacePath": "/Users/jp/.agents/plugins/marketplace.json",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "id": 2,
                        "result": {
                            "data": [
                                {
                                    "warnings": [],
                                    "errors": [],
                                    "hooks": [
                                        {
                                            "pluginId": "ticket@turbo-mode",
                                            "eventName": "preToolUse",
                                            "matcher": "Bash",
                                            "command": guard_command,
                                            "sourcePath": f"{plugin_root}/hooks/hooks.json",
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
        runtime_probe_output=probe_output,
    )

    assert report["runtime"]["live_hook_probe"] == "proven"
    assert report["runtime"]["ticket_plugin_enabled"] is True
    assert report["runtime"]["ticket_hook_count"] == 1


def test_ticket_doctor_blocks_wrong_hook_event(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    guard_command = _manifest_guard_command(plugin_root)
    probe_output = tmp_path / "wrong-event.out"
    probe_output.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": 1,
                        "result": {
                            "plugin": {
                                "summary": {
                                    "id": "ticket@turbo-mode",
                                    "enabled": True,
                                    "installed": True,
                                },
                                "marketplacePath": "/Users/jp/.agents/plugins/marketplace.json",
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "id": 2,
                        "result": {
                            "data": [
                                {
                                    "warnings": [],
                                    "errors": [],
                                    "hooks": [
                                        {
                                            "pluginId": "ticket@turbo-mode",
                                            "eventName": "postToolUse",
                                            "matcher": "Bash",
                                            "command": guard_command,
                                            "sourcePath": f"{plugin_root}/hooks/hooks.json",
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
        runtime_probe_output=probe_output,
    )

    assert report["runtime"]["live_hook_probe"] == "blocked"
    assert report["runtime"]["ticket_plugin_enabled"] is True
    assert report["runtime"]["ticket_hook_count"] == 0


@pytest.mark.parametrize("bad_root", [Path("/"), Path("/Users/jp")])
def test_ticket_doctor_rejects_arbitrary_plugin_roots(tmp_tickets: Path, bad_root: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]

    with pytest.raises(DoctorInputError, match="plugin_root"):
        ticket_doctor(tmp_tickets, plugin_root=bad_root, cache_root=plugin_root)


def test_ticket_doctor_rejects_unrelated_cache_root(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    unrelated = tmp_path / "unrelated-cache"
    unrelated.mkdir()

    with pytest.raises(DoctorInputError, match="cache_root"):
        ticket_doctor(tmp_tickets, plugin_root=plugin_root, cache_root=unrelated)


def test_cli_doctor_rejects_arbitrary_roots(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            "python3",
            "-B",
            str(plugin_root / "scripts" / "ticket_triage.py"),
            "doctor",
            str(tmp_tickets),
            "--plugin-root",
            "/",
            "--cache-root",
            "/",
        ],
        cwd=str(tmp_tickets.parent.parent),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    output = json.loads(completed.stdout)
    assert output["state"] == "escalate"
    assert output["error_code"] == "invalid_doctor_root"


def test_ticket_doctor_wrapper_rejects_fix_without_confirmation(tmp_tickets: Path) -> None:
    completed = subprocess.run(
        ["python3", "-B", str(DOCTOR_SCRIPT), "repair-audit", str(tmp_tickets), "--fix"],
        cwd=str(tmp_tickets.parent.parent),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "--confirm-repair" in completed.stderr


def test_tree_manifest_enforces_scale_limits(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b.txt").write_text("b", encoding="utf-8")

    with pytest.raises(DoctorInputError, match="file count"):
        _tree_manifest(root, max_files=1, max_bytes=100)

    with pytest.raises(DoctorInputError, match="hashed bytes"):
        _tree_manifest(root, max_files=10, max_bytes=1)

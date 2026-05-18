from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.support.builders import make_ticket

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
READ_SCRIPT = PLUGIN_ROOT / "scripts" / "ticket_read.py"
REVIEW_SCRIPT = PLUGIN_ROOT / "scripts" / "ticket_review.py"
DOCTOR_SCRIPT = PLUGIN_ROOT / "scripts" / "ticket_doctor.py"


def _run_json(command: list[str], *, cwd: Path) -> tuple[int, dict]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.stderr == ""
    return completed.returncode, json.loads(completed.stdout)


def _audit_file_has_corrupt_line(path: Path) -> bool:
    return "NOT JSON" in path.read_text(encoding="utf-8")


def test_find_open_list_groups_needs_refinement_separately(tmp_tickets: Path) -> None:
    make_ticket(
        tmp_tickets,
        "ready.md",
        id="T-20260518-01",
        title="Ready work",
        status="open",
        priority="high",
    )
    make_ticket(
        tmp_tickets,
        "needs-refinement.md",
        id="T-20260518-02",
        title="Needs more capture",
        status="open",
        priority="critical",
        extra_yaml="refinement_status: needs_refinement\n        ",
    )

    returncode, output = _run_json(
        [sys.executable, "-B", str(READ_SCRIPT), "list", str(tmp_tickets), "--status", "open"],
        cwd=tmp_tickets.parent.parent,
    )

    assert returncode == 0
    groups = output["data"]["ticket_groups"]
    assert [ticket["id"] for ticket in groups["needs_refinement"]] == ["T-20260518-02"]
    assert [ticket["id"] for ticket in groups["ready"]] == ["T-20260518-01"]


def test_review_output_suggests_capture_prompts_without_writing_tickets(tmp_tickets: Path) -> None:
    ticket_path = make_ticket(
        tmp_tickets,
        "needs-refinement.md",
        id="T-20260518-03",
        title="Captured placeholder",
        status="open",
        priority="medium",
        extra_yaml="refinement_status: needs_refinement\n        ",
    )
    before = {path: path.read_text(encoding="utf-8") for path in tmp_tickets.glob("*.md")}

    returncode, output = _run_json(
        [sys.executable, "-B", str(REVIEW_SCRIPT), "review", str(tmp_tickets)],
        cwd=tmp_tickets.parent.parent,
    )

    assert returncode == 0
    prompts = output["data"]["suggested_capture_prompts"]
    assert prompts == [
        {
            "ticket_id": "T-20260518-03",
            "prompt": "Use ticket-capture to refine T-20260518-03: Captured placeholder",
        }
    ]
    assert ticket_path.read_text(encoding="utf-8") == before[ticket_path]
    assert {path.name for path in tmp_tickets.glob("*.md")} == {path.name for path in before}


def test_review_audit_request_stays_on_review_backend(tmp_tickets: Path) -> None:
    returncode, output = _run_json(
        [sys.executable, "-B", str(REVIEW_SCRIPT), "audit", str(tmp_tickets)],
        cwd=tmp_tickets.parent.parent,
    )

    assert returncode == 0
    assert output["data"]["backend"] == "ticket_triage.audit"
    assert "doctor" not in output["data"]


def test_doctor_diagnose_is_read_only_by_default(tmp_tickets: Path) -> None:
    before = sorted(path.relative_to(tmp_tickets).as_posix() for path in tmp_tickets.rglob("*"))

    returncode, output = _run_json(
        [
            sys.executable,
            "-B",
            str(DOCTOR_SCRIPT),
            "diagnose",
            str(tmp_tickets),
            "--plugin-root",
            str(PLUGIN_ROOT),
            "--cache-root",
            str(PLUGIN_ROOT),
        ],
        cwd=tmp_tickets.parent.parent,
    )

    after = sorted(path.relative_to(tmp_tickets).as_posix() for path in tmp_tickets.rglob("*"))
    assert returncode == 0
    assert output["data"]["mode"] == "diagnose"
    assert output["data"]["read_only"] is True
    assert after == before


def test_doctor_audit_repair_dry_runs_before_mutation(tmp_tickets: Path) -> None:
    audit_dir = tmp_tickets / ".audit" / "2026-05-18"
    audit_dir.mkdir(parents=True)
    audit_file = audit_dir / "session.jsonl"
    audit_file.write_text('{"action": "create"}\nNOT JSON\n', encoding="utf-8")

    returncode, output = _run_json(
        [sys.executable, "-B", str(DOCTOR_SCRIPT), "repair-audit", str(tmp_tickets)],
        cwd=tmp_tickets.parent.parent,
    )

    assert returncode == 0
    assert output["data"]["dry_run"]["data"]["corrupt_files"] == 1
    assert output["data"]["repair"] is None
    assert _audit_file_has_corrupt_line(audit_file)


def test_doctor_audit_repair_requires_explicit_confirmation(tmp_tickets: Path) -> None:
    audit_dir = tmp_tickets / ".audit" / "2026-05-18"
    audit_dir.mkdir(parents=True)
    audit_file = audit_dir / "session.jsonl"
    audit_file.write_text('{"action": "create"}\nNOT JSON\n', encoding="utf-8")

    unconfirmed_returncode, unconfirmed = _run_json(
        [sys.executable, "-B", str(DOCTOR_SCRIPT), "repair-audit", str(tmp_tickets)],
        cwd=tmp_tickets.parent.parent,
    )
    confirmed_returncode, confirmed = _run_json(
        [
            sys.executable,
            "-B",
            str(DOCTOR_SCRIPT),
            "repair-audit",
            str(tmp_tickets),
            "--confirm-repair",
        ],
        cwd=tmp_tickets.parent.parent,
    )

    assert unconfirmed_returncode == 0
    assert unconfirmed["data"]["requires_confirmation"] is True
    assert confirmed_returncode == 0
    assert confirmed["data"]["dry_run"]["data"]["corrupt_files"] == 1
    assert confirmed["data"]["repair"]["data"]["repaired_files"] == [str(audit_file)]
    assert not _audit_file_has_corrupt_line(audit_file)

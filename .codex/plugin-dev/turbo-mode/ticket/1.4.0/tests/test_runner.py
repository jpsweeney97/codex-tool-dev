"""Tests for ticket_engine_runner.py — in-process boundary logic tests."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_engine_runner import run


def _write_payload(tmp_path: Path, payload: dict) -> str:
    """Write payload to a temp file and return the path string."""
    p = tmp_path / "input.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def _ensure_project_root(tmp_path: Path) -> None:
    """Create a .git marker so discover_project_root() succeeds."""
    (tmp_path / ".git").mkdir(exist_ok=True)


class TestUsageErrors:
    def test_missing_args_returns_1(self, capsys, tmp_path):
        code = run("user", [], prog="ticket_engine_user.py")
        assert code == 1
        err = capsys.readouterr().err
        assert "Usage:" in err

    def test_one_arg_returns_1(self, capsys, tmp_path):
        code = run("user", ["classify"], prog="ticket_engine_user.py")
        assert code == 1
        err = capsys.readouterr().err
        assert "Usage:" in err

    def test_prog_appears_in_usage(self, capsys):
        run("user", [], prog="my_custom_prog.py")
        err = capsys.readouterr().err
        assert "my_custom_prog.py" in err


class TestPayloadReadErrors:
    def test_missing_file_returns_1(self, capsys, tmp_path):
        _ensure_project_root(tmp_path)
        code = run(
            "user",
            ["classify", str(tmp_path / "nonexistent.json")],
            prog="ticket_engine_user.py",
        )
        assert code == 1
        err = capsys.readouterr().err
        assert "Cannot read payload" in err

    def test_bad_json_returns_1(self, capsys, tmp_path):
        _ensure_project_root(tmp_path)
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        code = run(
            "user",
            ["classify", str(bad_file)],
            prog="ticket_engine_user.py",
        )
        assert code == 1
        err = capsys.readouterr().err
        assert "Cannot read payload" in err


class TestOriginMismatch:
    def test_user_entrypoint_rejects_agent_hook_origin(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "args": {},
            "session_id": "test",
            "hook_request_origin": "agent",
        })
        code = run("user", ["classify", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "origin_mismatch"

    def test_agent_entrypoint_rejects_user_hook_origin(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "args": {},
            "session_id": "test",
            "hook_request_origin": "user",
        })
        code = run("agent", ["classify", payload_file], prog="ticket_engine_agent.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "origin_mismatch"


class TestTrustTriple:
    def test_execute_without_hook_injected(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "fields": {"title": "t", "problem": "p"},
            "session_id": "test",
        })
        code = run("user", ["execute", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "policy_blocked"

    def test_execute_with_empty_session_id(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "fields": {"title": "t", "problem": "p"},
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "",
        })
        code = run("user", ["execute", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "policy_blocked"

    def test_execute_without_hook_request_origin(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "fields": {"title": "t", "problem": "p"},
            "hook_injected": True,
            "session_id": "test",
        })
        code = run("user", ["execute", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "policy_blocked"


class TestProjectRoot:
    def test_no_project_root_returns_policy_blocked(self, capsys, tmp_path, monkeypatch):
        # tmp_path has NO .git or .codex marker.
        nested = tmp_path / "no" / "markers"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        payload_file = _write_payload(nested, {
            "action": "create",
            "args": {},
            "session_id": "test",
        })
        code = run("user", ["classify", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["state"] == "policy_blocked"
        assert "project root" in out["message"]


class TestTicketsDir:
    def test_tickets_dir_outside_root_returns_policy_blocked(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside-tickets"
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "args": {},
            "session_id": "test",
            "tickets_dir": str(outside),
        })
        code = run("user", ["classify", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["state"] == "policy_blocked"


class TestSuccessfulDispatch:
    def test_classify_returns_0(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "args": {},
            "session_id": "test",
        })
        code = run("user", ["classify", payload_file], prog="ticket_engine_user.py")
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["state"] == "ok"

    def test_execute_with_full_trust_triple_returns_0(self, capsys, tmp_path, monkeypatch):
        from scripts.ticket_dedup import dedup_fingerprint as compute_fp

        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        problem = "test problem"
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "fields": {"title": "Test", "problem": problem, "priority": "medium"},
            "hook_injected": True,
            "hook_request_origin": "user",
            "session_id": "test-session",
            "classify_intent": "create",
            "classify_confidence": 0.95,
            "dedup_fingerprint": compute_fp(problem, []),
        })
        code = run("user", ["execute", payload_file], prog="ticket_engine_user.py")
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["state"] == "ok_create"


class TestPayloadValidation:
    def test_bad_field_type_returns_parse_error(self, capsys, tmp_path, monkeypatch):
        """PayloadError from stage models is caught and returned as structured JSON."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": 123,  # Must be a string — triggers PayloadError.
            "args": {},
            "session_id": "test",
        })
        code = run("user", ["classify", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "parse_error"
        assert "classify" in out["message"].lower()


class TestExitCodes:
    def test_need_fields_returns_2(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        # Plan with empty fields triggers need_fields for create intent.
        payload_file = _write_payload(tmp_path, {
            "intent": "create",
            "fields": {},
            "session_id": "test",
        })
        code = run("user", ["plan", payload_file], prog="ticket_engine_user.py")
        assert code == 2
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "need_fields"

    def test_unknown_subcommand_returns_1(self, capsys, tmp_path, monkeypatch):
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        payload_file = _write_payload(tmp_path, {
            "action": "create",
            "args": {},
            "session_id": "test",
        })
        code = run("user", ["bogus", payload_file], prog="ticket_engine_user.py")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["error_code"] == "intent_mismatch"

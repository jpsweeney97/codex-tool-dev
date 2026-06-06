from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
COMMAND_SKILLS = [
    PLUGIN_ROOT / "skills" / "search-handoffs" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "distill" / "SKILL.md",
]
STATE_SKILLS = [
    PLUGIN_ROOT / "skills" / "load-handoff" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "save-handoff" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "quicksave" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "save-summary" / "SKILL.md",
]
LOAD_SKILL = PLUGIN_ROOT / "skills" / "load-handoff" / "SKILL.md"
CHAIN_STATE_SKILLS = [
    PLUGIN_ROOT / "skills" / "save-handoff" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "quicksave" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "save-summary" / "SKILL.md",
]


def test_no_skill_doc_uses_relative_script_paths() -> None:
    for path in COMMAND_SKILLS + STATE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "../../scripts/" not in text


def test_skill_docs_do_not_request_tool_permissions_up_front() -> None:
    for path in COMMAND_SKILLS + STATE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "allowed-tools" not in text


def test_command_skills_define_plugin_root_setup() -> None:
    for path in COMMAND_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Resolve plugin root" in text
        assert "three levels above this `SKILL.md`" in text
        assert "not the `skills/` directory" in text
        assert 'PLUGIN_ROOT="/absolute/path/to/handoff"' in text
        assert "two levels above" not in text
        assert 'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff"' in text
        assert "PYTHONDONTWRITEBYTECODE=1" in text


def test_state_skills_use_session_state_module() -> None:
    for path in CHAIN_STATE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Resolve plugin root" in text
        assert "three levels above this `SKILL.md`" in text
        assert "not the `skills/` directory" in text
        assert 'PLUGIN_ROOT="/absolute/path/to/handoff"' in text
        assert "session_state.py" in text
        assert 'python "$PLUGIN_ROOT/scripts/session_state.py"' in text
        assert "begin-active-write" in text
        assert "write-active-handoff" in text
        assert "operation_state_path" in text
        assert "allocated_active_path" in text
        assert "resumed_from_path" in text
        assert "<project_root>/.codex/handoffs/" in text
        assert "read-state" not in text
        assert "clear-state" not in text
        assert "$PROJECT_ROOT/docs/handoffs/.session-state" not in text
        assert "legacy plain-text state file" not in text
        assert "The literal `python` command must resolve to Python >=3.11." in text
        assert "PYTHONDONTWRITEBYTECODE=1" in text
        assert "UV_PROJECT_ENVIRONMENT" not in text
        assert "uv run --project" not in text


def test_load_skill_uses_load_transaction_and_listing_scripts() -> None:
    text = LOAD_SKILL.read_text(encoding="utf-8")
    assert "Resolve plugin root" in text
    assert "three levels above this `SKILL.md`" in text
    assert "not the `skills/` directory" in text
    assert 'PLUGIN_ROOT="/absolute/path/to/handoff"' in text
    assert 'python "$PLUGIN_ROOT/scripts/load_transactions.py"' in text
    assert 'python "$PLUGIN_ROOT/scripts/list_handoffs.py"' in text
    assert "<project_root>/.codex/handoffs/archive/<filename>" in text
    assert (
        "<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json"
        in text
    )
    assert 'load_transactions.py" \\' in text
    assert "session_state.py" not in text
    assert 'ls "$(git rev-parse --show-toplevel)/docs/handoffs"' not in text
    assert '--archive-dir "$PROJECT_ROOT/docs/handoffs/archive"' not in text


def test_load_skill_documents_fail_closed_operator_recovery_boundaries() -> None:
    text = LOAD_SKILL.read_text(encoding="utf-8")

    assert "Readable pending load transactions are recovered before a new load is selected" in text
    assert "Unreadable or corrupt transaction records block `/load`" in text
    assert "global fail-closed" in text
    assert "recovery claim file present" in text
    assert "stale lock from another host" in text
    assert "operator review" in text
    assert "Pending interrupted loads are recovered before a new load is selected" not in text
    assert "Re-run `/load`; pending transactions are recovered before new selection" not in text


def test_ticket_backed_skills_are_not_active() -> None:
    assert not (PLUGIN_ROOT / "skills" / "defer").exists()
    assert not (PLUGIN_ROOT / "skills" / "triage").exists()

from __future__ import annotations

from pathlib import Path


PLUGIN_ROOT = Path(__file__).parent.parent
COMMAND_SKILLS = [
    PLUGIN_ROOT / "skills" / "search" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "distill" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "triage" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "defer" / "SKILL.md",
]
STATE_SKILLS = [
    PLUGIN_ROOT / "skills" / "load" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "save" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "quicksave" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "summary" / "SKILL.md",
]


def test_no_skill_doc_uses_relative_script_paths() -> None:
    for path in COMMAND_SKILLS + STATE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "../../scripts/" not in text


def test_command_skills_define_plugin_root_setup() -> None:
    for path in COMMAND_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Resolve plugin root" in text
        assert "three levels above this `SKILL.md`" in text
        assert "not the `skills/` directory" in text
        assert 'PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"' in text
        assert "two levels above" not in text
        assert 'UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0"' in text
        assert "PYTHONDONTWRITEBYTECODE=1" in text


def test_state_skills_use_session_state_module() -> None:
    for path in STATE_SKILLS:
        text = path.read_text(encoding="utf-8")
        assert "Resolve plugin root" in text
        assert "three levels above this `SKILL.md`" in text
        assert "not the `skills/` directory" in text
        assert 'PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"' in text
        assert "session_state.py" in text
        assert "handoff-<project>-<resume_token>.json" in text
        assert "legacy plain-text state file" in text
        assert 'python "$PLUGIN_ROOT/scripts/session_state.py"' in text
        assert "The literal `python` command must resolve to Python >=3.11." in text
        assert "PYTHONDONTWRITEBYTECODE=1" in text
        assert "UV_PROJECT_ENVIRONMENT" not in text
        assert "uv run --project" not in text


def test_defer_skill_uses_plugin_siblings_plain_field() -> None:
    text = (PLUGIN_ROOT / "skills" / "defer" / "SKILL.md").read_text(encoding="utf-8")
    assert 'plugin_siblings.py" --plugin-root "$PLUGIN_ROOT" --sibling ticket --field plugin_root' in text
    assert 'python "$PLUGIN_ROOT/scripts/defer.py" --tickets-dir "$PROJECT_ROOT/docs/tickets"' in text
    assert (
        'python3 /absolute/ticket/root/scripts/ticket_engine_user.py ingest "$PROJECT_ROOT/.codex/ticket-tmp/payload-'
        in text
    )
    assert "relative payload path" in text
    assert "$TICKET_PLUGIN_ROOT" not in text
    assert "/tmp/ingest_payload.json" not in text
    assert "../../../../ticket/" not in text
    assert "ticket/1.4.0/scripts" not in text

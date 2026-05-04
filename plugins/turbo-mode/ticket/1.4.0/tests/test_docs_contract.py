"""Static contract checks for current-facing docs and skill files."""
from __future__ import annotations

import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = [
    PLUGIN_ROOT / "skills" / "ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-triage" / "SKILL.md",
]
CURRENT_FACING_DOCS = SKILL_FILES + [
    PLUGIN_ROOT / "skills" / "ticket" / "references" / "pipeline-guide.md",
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
]
NO_FLAG_LAUNCHER_RE = re.compile(r"python3\s+(?!-B\b)<[^>]+>/scripts/[^\s`]+")
COUNTED_TESTS_RE = re.compile(r"\b\d+\s+tests?\b")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ticket_skill_resolves_plugin_root_three_levels_up() -> None:
    text = _read_text(PLUGIN_ROOT / "skills" / "ticket" / "SKILL.md")
    assert "three levels above this `SKILL.md`" in text


def test_ticket_triage_skill_resolves_plugin_root_three_levels_up() -> None:
    text = _read_text(PLUGIN_ROOT / "skills" / "ticket-triage" / "SKILL.md")
    assert "three levels above this `SKILL.md`" in text


def test_skill_docs_use_project_root_marker_walk_not_git_rev_parse() -> None:
    for path in CURRENT_FACING_DOCS:
        assert "git rev-parse --show-toplevel" not in _read_text(path), str(path)


def test_skill_docs_define_project_root_and_tickets_dir_separately() -> None:
    for path in SKILL_FILES:
        text = _read_text(path)
        assert "PROJECT_ROOT" in text, str(path)
        assert "TICKETS_DIR" in text, str(path)
        assert "PLUGIN_ROOT" in text, str(path)


def test_current_facing_docs_include_dash_b_launcher_examples() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read_text(path)
        if "scripts/" in text:
            assert "python3 -B <PLUGIN_ROOT>/scripts/" in text, str(path)


def test_current_facing_docs_do_not_keep_no_flag_plugin_launchers() -> None:
    for path in CURRENT_FACING_DOCS:
        assert not NO_FLAG_LAUNCHER_RE.search(_read_text(path)), str(path)


def test_handbook_does_not_advertise_stale_test_count_or_version_footer() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "596 passed" not in text
    assert "Plugin v1.2.0" not in text


def test_readme_and_handbook_do_not_advertise_counted_test_inventory() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        assert not COUNTED_TESTS_RE.search(_read_text(path)), str(path)


def test_ticket_skill_uses_workflow_runner_as_primary_mutation_path() -> None:
    text = (PLUGIN_ROOT / "skills" / "ticket" / "SKILL.md").read_text(encoding="utf-8")
    primary = text.split("## Read Operations", 1)[0]
    assert "ticket_workflow.py prepare" in text
    assert "ticket_workflow.py execute" in text
    assert "<PLUGIN_ROOT>/scripts/ticket_workflow.py prepare <PAYLOAD_PATH>" in text
    assert "<PROJECT_ROOT>/.codex/ticket-tmp/" in text
    assert "absolute `PAYLOAD_PATH`" in text
    assert "Unified Preview" in text
    assert "Recovery Options" in text
    assert "recover_command" in text
    assert "run the returned `recover_command`" in text
    assert "4-stage engine pipeline" not in primary
    assert "classify → plan → preflight → execute" not in primary
    for operation in ("create", "update", "close", "reopen"):
        routing_line = next(line for line in text.splitlines() if line.startswith(f"| `{operation}` |"))
        assert "ticket_workflow.py prepare" in routing_line
        assert "Engine pipeline" not in routing_line


def test_ticket_skill_documents_check_and_doctor() -> None:
    ticket_text = (PLUGIN_ROOT / "skills" / "ticket" / "SKILL.md").read_text(encoding="utf-8")
    triage_text = (PLUGIN_ROOT / "skills" / "ticket-triage" / "SKILL.md").read_text(encoding="utf-8")
    assert "ticket_read.py check" in ticket_text
    assert "ticket_triage.py doctor" in triage_text
    assert "<CACHE_ROOT>" in triage_text
    assert "/Users/jp/.codex/plugins/cache/" not in ticket_text
    assert "/Users/jp/.codex/plugins/cache/" not in triage_text


def test_readme_documents_ticket_ux_commands() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    assert "ticket_workflow.py" in text
    assert "ticket_read.py` | `check" in text
    assert "ticket_triage.py` | `doctor" in text


def test_contract_preserves_engine_boundary_for_workflow_runner() -> None:
    text = (PLUGIN_ROOT / "references" / "ticket-contract.md").read_text(encoding="utf-8")
    assert "Workflow runner" in text
    assert "prepare" in text
    assert "execute" in text
    assert "recover" in text
    assert "does not replace the engine interface" in text

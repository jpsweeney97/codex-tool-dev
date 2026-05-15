from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
POLICY_DOCS = [
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "references" / "handoff-contract.md",
    PLUGIN_ROOT / "skills" / "load" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "save" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "quicksave" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "summary" / "SKILL.md",
]
CURRENT_STORAGE_DOCS = [
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "references" / "handoff-contract.md",
    PLUGIN_ROOT / "references" / "format-reference.md",
]
CHAIN_WRITER_DOCS = [
    PLUGIN_ROOT / "skills" / "save" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "quicksave" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "summary" / "SKILL.md",
]
STATE_WRITER_DOCS = [
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "references" / "handoff-contract.md",
    PLUGIN_ROOT / "skills" / "load" / "SKILL.md",
]
POLICY_CODE_COMMENTS = [
    PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "cleanup.py",
    PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "project_paths.py",
]
EXPECTED_VERSION = "1.7.0"


def test_versions_are_aligned() -> None:
    plugin_json = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    pyproject = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert plugin_json["version"] == EXPECTED_VERSION
    assert pyproject["project"]["version"] == EXPECTED_VERSION


def test_readme_documents_current_summary_and_development_commands() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    assert "codex plugin install ./plugins/turbo-mode/handoff/1.6.0" in text
    assert "cd plugins/turbo-mode/handoff/1.6.0" in text
    assert "uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest" in text
    assert "pytest --collect-only -q" in text
    assert "/summary" in text
    assert "`handoff`, `checkpoint`, or `summary`" in text
    assert "./packages/plugins/handoff" not in text
    assert "cd packages/plugins/handoff" not in text
    assert "uv run --package handoff-plugin pytest" not in text
    assert "354 tests across 10 test modules" not in text


def test_docs_do_not_claim_universal_gitignore_policy() -> None:
    for path in POLICY_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "gitignored at the repository level" not in text
        assert "local-only working memory" not in text
        assert "host-repository policy" in text
        assert "does not add gitignore rules" in text


def test_docs_use_resume_token_state_shape() -> None:
    for path in STATE_WRITER_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "handoff-<project>-<resume_token>.json" in text


def test_chain_writer_docs_use_active_writer_state_bridge() -> None:
    for path in CHAIN_WRITER_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "begin-active-write" in text
        assert "write-active-handoff" in text
        assert "resumed_from_path" in text
        assert "handoff-<project>-<resume_token>.json" not in text


def test_current_storage_docs_name_codex_handoffs_as_primary_storage() -> None:
    for path in CURRENT_STORAGE_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "<project_root>/.codex/handoffs/" in text
        assert "<project_root>/docs/handoffs/" not in text
        assert "local-only working memory" not in text


def test_changelog_records_handoff_storage_reversal() -> None:
    text = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert (
        "Handoff storage moved from `<project_root>/docs/handoffs/` "
        "to `<project_root>/.codex/handoffs/`"
    ) in text
    assert (
        "Handoff storage moved from `<project_root>/.codex/handoffs/` "
        "to `<project_root>/docs/handoffs/`"
    ) not in text
    assert "local-only working memory" not in text


def test_internal_comments_do_not_assert_gitignored_or_local_only_policy() -> None:
    for path in POLICY_CODE_COMMENTS:
        text = path.read_text(encoding="utf-8")
        assert "gitignored to avoid tracking ephemeral session artifacts" not in text
        assert "local-only working memory" not in text
        assert "host-repository policy" in text


def test_readme_does_not_publish_bundled_hook_launcher_contract() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    assert '"command": "./hooks/run_cleanup.py"' not in text
    assert '"command": "./hooks/run_quality_check.py"' not in text
    assert "plugin-bundled command hooks are deferred from 1.6.0" in text
    assert "does not ship plugin-bundled command hooks" in text
    assert "| **Automatic maintenance** | *(hooks)* |" not in text
    assert "python3 /absolute/path/to/plugin/scripts/my-script.py" not in text


def test_load_skill_does_not_instruct_plugin_managed_gitignore() -> None:
    text = (PLUGIN_ROOT / "skills" / "load" / "SKILL.md").read_text(encoding="utf-8")
    assert ".gitignore" not in text
    assert "does not ship plugin-bundled command hooks" in text
    assert "SessionStart hook runs silently" not in text


def test_changelog_has_1_7_0_release_header() -> None:
    text = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^## \[1\.7\.0\] - 2026-05-15$", text, re.MULTILINE), text
    assert re.search(r"^## \[1\.6\.0\] - \d{4}-\d{2}-\d{2}$", text, re.MULTILINE), text

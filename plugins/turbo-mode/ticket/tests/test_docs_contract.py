"""Static contract checks for current-facing docs and skill files."""
from __future__ import annotations

import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SKILL = PLUGIN_ROOT / "skills" / "ticket-capture" / "SKILL.md"
SKILL_FILES = [
    CAPTURE_SKILL,
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


def _strip_frontmatter_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _frontmatter(text: str) -> dict[str, str | list[str]]:
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    data: dict[str, str | list[str]] = {}
    current_key = ""
    for line in lines[1:end]:
        if line and not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            current_key = key
            value = value.strip()
            data[key] = _strip_frontmatter_scalar(value) if value else []
        elif current_key and line.startswith("  - "):
            current_value = data[current_key]
            assert isinstance(current_value, list)
            current_value.append(_strip_frontmatter_scalar(line[4:].strip()))
    return data


def test_ticket_capture_skill_exists() -> None:
    assert CAPTURE_SKILL.exists()


def test_ticket_capture_skill_frontmatter_matches_task3_contract() -> None:
    text = _read_text(CAPTURE_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-capture"
    assert frontmatter["allowed-tools"] == ["Bash", "Write", "Read"]
    assert "argument-hint" not in text

    description = frontmatter["description"]
    assert isinstance(description, str)
    for snippet in (
        "Create repo-local tickets from natural language capture intent",
        "track, file, capture, ticket, or remember",
        "bug, feature, follow-up, task, or cleanup item",
        "Infer aggressively",
        "require explicit confirmation before writing",
        "Do not trigger from casual statements like 'this is a bug'",
        "unless the user also asks to track or file it",
    ):
        assert snippet in description


def test_ticket_capture_skill_contains_exact_compact_preview_labels() -> None:
    text = _read_text(CAPTURE_SKILL)
    for label in (
        "Capture ticket",
        "Title: <synthesized title>",
        "Problem: <1-2 sentence synthesized problem>",
        "Next action: <single concrete next step>",
        "Confidence: low|medium|high",
        'Duplicate: none | possible T-... "<title>"',
        "Create this ticket? [create / edit / cancel]",
    ):
        assert label in text


def test_ticket_capture_skill_forbids_raw_user_wording() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "Never store raw user wording" in text
    assert "do not write verbatim transcript text" in text
    assert "raw_user_text" in text
    assert "raw_request" in text
    assert "transcript_excerpt" in text


def test_ticket_capture_skill_requires_explicit_confirmation_before_writing() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "Require explicit `create` confirmation before writing" in text
    assert "Do not treat silence" in text


def test_ticket_capture_skill_uses_canonical_prepare_and_execute_commands() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert (
        "python3 -B <PLUGIN_ROOT>/scripts/ticket_capture.py prepare <PAYLOAD_PATH>"
        in text
    )
    assert (
        "python3 -B <PLUGIN_ROOT>/scripts/ticket_capture.py execute <PAYLOAD_PATH>"
        in text
    )


def test_ticket_capture_skill_documents_path_resolution_contract() -> None:
    text = _read_text(CAPTURE_SKILL)
    for snippet in (
        "Resolve these paths before writing the payload or running commands",
        "`PLUGIN_ROOT`:",
        "`PROJECT_ROOT`:",
        "`TICKETS_DIR`:",
        "`PAYLOAD_PATH`: an absolute path",
        "<PROJECT_ROOT>/.codex/ticket-tmp/",
        "do not use a relative path",
    ):
        assert snippet in text


def test_ticket_capture_skill_documents_required_synthesized_fields() -> None:
    text = _read_text(CAPTURE_SKILL)
    for field in (
        "title",
        "captured_request",
        "problem",
        "next_action",
        "capture_confidence",
        "priority",
        "tags",
        "component",
        "related_paths",
        "acceptance_criteria",
    ):
        assert f"`capture.{field}`" in text


def test_ticket_capture_skill_keeps_provenance_hook_owned() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "with a `capture` object only" in text
    assert "Do not\nwrite `session_id`, `hook_injected`, or `hook_request_origin`" in text
    assert "hook/provenance fields are hook-owned" in text
    assert "injected by the canonical command\npath" in text
    assert "Top-level fields: `tickets_dir`, `session_id`" not in text


def test_ticket_capture_skill_documents_deterministic_inference_boundaries() -> None:
    text = _read_text(CAPTURE_SKILL)
    for snippet in (
        "Default priority to `medium`",
        "Set priority to `critical` only for explicit production, data-loss, security",
        "or release-blocking language",
        "Set priority to `high` only for explicit blocker, regression, CI-red, or",
        "cannot-ship language",
        "Set priority to `low` only for explicit cleanup, polish, or nice-to-have",
        "controlled tags only: `needs-refinement`, `bug`, `feature`,",
        "`docs`, `test`, `maintenance`, and `security`",
        "Do not invent component tags",
        "Set `related_paths` only from explicit user text and files immediately",
        "discussed in the current turn",
        "Do not scan the whole git diff by default",
        "Set `component` only when user-supplied or obvious from explicit paths",
    ):
        assert snippet in text


def test_ticket_capture_skill_documents_refinement_and_preview_rules() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "Ask one follow-up only when no useful `next_action` can be" in text
    assert "synthesized" in text
    assert "Show `Priority: <priority>` only when priority is not `medium`" in text
    assert "or confidence is" in text
    assert "`low`" in text


def test_ticket_capture_skill_documents_create_edit_cancel_handling() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "`create`: run execute for the same `PAYLOAD_PATH`" in text
    assert "`edit`: safely update the payload with the scoped edit" in text
    assert "rerun the\n  canonical prepare command for the same `PAYLOAD_PATH`" in text
    assert "Do not put free-form\n  edit text on the shell command line" in text
    assert "--edit <text>" not in text
    assert "`cancel`: stop without writing a ticket" in text


def test_ticket_capture_skill_documents_split_deferral_behavior() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "If the user asks to split multiple items" in text
    assert "capture the first or clearest ticket" in text
    assert "After creation, show a suggested second capture prompt" in text


def test_ticket_capture_skill_preserves_hook_guard_boundary() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "Execute requires the prepared payload and hook/provenance path injected by the" in text
    assert "canonical command path" in text
    assert "Do not bypass" in text
    assert "the guard or use noncanonical commands" in text


def test_ticket_capture_skill_owns_creation_without_broad_ticket_skill() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "ticket_capture.py prepare" in text
    assert "ticket_capture.py execute" in text
    assert "ticket_workflow.py" not in text
    assert "`/ticket`" not in text
    assert "skills/ticket/SKILL.md" not in text


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

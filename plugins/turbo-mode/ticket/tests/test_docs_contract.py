"""Static contract checks for current-facing docs and skill files."""
from __future__ import annotations

import json
import re
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SKILL = PLUGIN_ROOT / "skills" / "ticket-capture" / "SKILL.md"
FIND_SKILL = PLUGIN_ROOT / "skills" / "ticket-find" / "SKILL.md"
UPDATE_SKILL = PLUGIN_ROOT / "skills" / "ticket-update" / "SKILL.md"
REVIEW_SKILL = PLUGIN_ROOT / "skills" / "ticket-review" / "SKILL.md"
DOCTOR_SKILL = PLUGIN_ROOT / "skills" / "ticket-doctor" / "SKILL.md"
NEW_SKILL_FILES = [
    CAPTURE_SKILL,
    FIND_SKILL,
    UPDATE_SKILL,
    REVIEW_SKILL,
    DOCTOR_SKILL,
]
REMOVED_SKILL_FILES = [
    PLUGIN_ROOT / "skills" / "ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-triage" / "SKILL.md",
]
SKILL_FILES = NEW_SKILL_FILES
CURRENT_FACING_DOCS = SKILL_FILES + [
    PLUGIN_ROOT / "skills" / "ticket" / "references" / "pipeline-guide.md",
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
]
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
NO_FLAG_LAUNCHER_RE = re.compile(r"python3\s+(?!-B\b)<[^>]+>/scripts/[^\s`]+")
COUNTED_TESTS_RE = re.compile(r"\b\d+\s+tests?\b")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _json_code_blocks(text: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for match in re.finditer(r"```json\n(.*?)\n```", text, re.DOTALL):
        parsed = json.loads(match.group(1))
        assert isinstance(parsed, dict)
        blocks.append(parsed)
    return blocks


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


def test_old_broad_skill_files_do_not_exist() -> None:
    for path in REMOVED_SKILL_FILES:
        assert not path.exists(), str(path)


def test_task4_split_skill_files_exist() -> None:
    for path in NEW_SKILL_FILES:
        assert path.exists(), str(path)


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


def test_new_split_skills_resolve_plugin_root_three_levels_up() -> None:
    for path in (FIND_SKILL, UPDATE_SKILL, REVIEW_SKILL, DOCTOR_SKILL):
        text = _read_text(path)
        assert "three levels above this `SKILL.md`" in text, str(path)


def test_ticket_find_skill_contract_is_read_only() -> None:
    text = _read_text(FIND_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-find"
    assert frontmatter["allowed-tools"] == ["Bash", "Read"]
    description = frontmatter["description"]
    assert isinstance(description, str)
    for snippet in (
        "Read, list, and search repo-local tickets",
        "show a ticket",
        "list tickets",
        "find tickets about a topic",
        "show open work",
        "check close readiness",
        "Read-only",
        "do not create, update, close, reopen, triage, or repair tickets",
    ):
        assert snippet in description
    assert "ticket_read.py list" in text
    assert "ticket_read.py query" in text
    assert "ticket_read.py check" in text
    assert "ticket_workflow.py" not in text
    assert "ticket_audit.py repair" not in text
    assert "Needs Refinement" in text
    assert "`refinement_status: needs_refinement`" in text
    assert "metadata, not a lifecycle status" in text


def test_ticket_update_skill_contract_is_preview_first_and_scoped() -> None:
    text = _read_text(UPDATE_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-update"
    assert frontmatter["allowed-tools"] == ["Bash", "Write", "Read"]
    description = frontmatter["description"]
    assert isinstance(description, str)
    for snippet in (
        "update a ticket",
        "mark work in progress",
        "close",
        "reopen",
        "change priority",
        "edit tags",
        "add blockers",
        "set component or related paths",
        "change capture metadata",
        "Requires preview before writing",
    ):
        assert snippet in description
    for unsupported_trigger in ("placeholder problem", "next action", "acceptance criteria"):
        assert unsupported_trigger not in description
    assert "Do not perform arbitrary body-section editing in v1" in text
    assert "Show the returned preview and wait for explicit user confirmation" in text
    assert "ticket_workflow.py prepare" in text
    assert "ticket_workflow.py execute" in text
    assert "There is no dedicated `ticket_update.py` backend yet" in text
    normalized = _normalize_whitespace(text)
    assert "existing-ticket lifecycle and frontmatter metadata updates" in normalized
    assert "rejects section fields such as `problem` and `acceptance_criteria`" in normalized
    assert "rejects unknown fields such as `next_action`" in normalized
    assert "future dedicated `ticket_update.py` backend from Task 5" in normalized
    assert "not available through the current workflow runner" in normalized
    assert '"action": "update"' in text
    assert '"action": "close"' in text
    assert '"action": "reopen"' in text
    assert '"ticket_id": "T-20260518-01"' in text
    assert '"args": {"ticket_id": "T-20260518-01"}' in text
    assert "fields" in text
    assert "Do not write `session_id`, `hook_injected`, or `hook_request_origin`" in normalized
    assert "canonical hook injects trust fields" in normalized


def test_ticket_update_json_examples_do_not_use_invalid_needs_refinement_tag() -> None:
    text = _read_text(UPDATE_SKILL)
    examples = _json_code_blocks(text)
    assert examples
    for example in examples:
        fields = example.get("fields")
        assert isinstance(fields, dict)
        tags = fields.get("tags")
        if isinstance(tags, list) and "needs-refinement" in tags:
            assert fields.get("refinement_status") == "needs_refinement"


def test_ticket_review_skill_contract_is_read_only_and_capture_prompt_only() -> None:
    text = _read_text(REVIEW_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-review"
    assert frontmatter["allowed-tools"] == ["Bash", "Read"]
    description = frontmatter["description"]
    assert isinstance(description, str)
    assert "Read-only" in description
    assert "may suggest capture prompts but must not write tickets" in description
    assert "ticket_triage.py dashboard" in text
    assert "ticket_triage.py audit" in text
    normalized = _normalize_whitespace(text)
    assert "Do not create, update, close, reopen, doctor, or repair tickets" in normalized
    assert "suggest a concrete `ticket-capture` prompt instead of writing the ticket" in normalized


def test_ticket_doctor_skill_contract_is_explicit_maintenance_only() -> None:
    text = _read_text(DOCTOR_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-doctor"
    assert frontmatter["allowed-tools"] == ["Bash", "Write", "Read"]
    description = frontmatter["description"]
    assert isinstance(description, str)
    assert "Run explicit Ticket plugin maintenance" in description
    assert "Use when the user explicitly asks to doctor the ticket system" in description
    assert "Do not use for casual audit, review, or triage" in description
    assert "diagnose ticket storage" in description
    assert "repair corrupt ticket audit logs" in description
    assert "validate ticket plugin health" in description
    assert "Do not trigger on casual audit, review, triage, or backlog-health language" in text
    assert "ticket_audit.py repair <TICKETS_DIR> --dry-run" in text
    assert "ask before any mutation" in text


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


def test_update_skill_uses_workflow_runner_as_mutation_path() -> None:
    text = _read_text(UPDATE_SKILL)
    assert "ticket_workflow.py prepare" in text
    assert "ticket_workflow.py execute" in text
    assert "<PLUGIN_ROOT>/scripts/ticket_workflow.py prepare <PAYLOAD_PATH>" in text
    assert "<PROJECT_ROOT>/.codex/ticket-tmp/" in text
    assert "absolute path under" in text
    assert "preview" in text
    assert "recover_command" in text
    normalized = _normalize_whitespace(text)
    assert "run only the returned recovery command" in normalized
    assert "ticket_update.py" in text


def test_split_skills_document_check_review_and_doctor_surfaces() -> None:
    find_text = _read_text(FIND_SKILL)
    review_text = _read_text(REVIEW_SKILL)
    doctor_text = _read_text(DOCTOR_SKILL)
    assert "ticket_read.py check" in find_text
    assert "ticket_triage.py dashboard" in review_text
    assert "ticket_triage.py audit" in review_text
    assert "ticket_triage.py doctor" not in review_text
    assert "ticket_triage.py doctor" in doctor_text
    assert "<CACHE_ROOT>" in doctor_text
    assert "/Users/jp/.codex/plugins/cache/" not in find_text
    assert "/Users/jp/.codex/plugins/cache/" not in review_text
    assert "/Users/jp/.codex/plugins/cache/" not in doctor_text


def test_readme_documents_ticket_ux_commands() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    assert "ticket_workflow.py" in text
    assert "ticket_read.py` | `check" in text
    assert "ticket_triage.py` | `doctor" in text


def test_plugin_default_prompts_are_capture_first() -> None:
    text = _read_text(MANIFEST)
    assert '"Track this follow-up"' in text
    assert '"Find open ticket work"' in text
    assert '"Review ticket backlog health"' in text
    assert '"Create a ticket for this work"' not in text
    assert '"Triage open tickets"' not in text
    assert '"Read the current ticket"' not in text


def test_no_skill_description_advertises_old_single_surface() -> None:
    old_surface_terms = {
        "create",
        "update",
        "close",
        "reopen",
        "list",
        "query",
        "audit repair",
    }
    for path in NEW_SKILL_FILES:
        description = _frontmatter(_read_text(path))["description"]
        assert isinstance(description, str)
        lowered = description.lower()
        assert not old_surface_terms.issubset(set(re.findall(r"[a-z]+(?: repair)?", lowered))), str(path)
        assert "create, update, close, reopen, list, query" not in lowered
        assert "full crud" not in lowered


def test_task4_docs_do_not_overclaim_current_placeholder_refinement() -> None:
    update_description = _frontmatter(_read_text(UPDATE_SKILL))["description"]
    assert isinstance(update_description, str)
    for unsupported in ("placeholder problem", "next action", "acceptance criteria"):
        assert unsupported not in update_description

    update_text = _normalize_whitespace(_read_text(UPDATE_SKILL))
    assert "rejects section fields such as `problem` and `acceptance_criteria`" in update_text
    assert "rejects unknown fields such as `next_action`" in update_text
    assert "future dedicated `ticket_update.py` backend from Task 5" in update_text
    assert "not available through the current workflow runner" in update_text

    readme = _read_text(PLUGIN_ROOT / "README.md")
    assert "placeholder-field updates through preview-first workflow commands" not in readme
    assert "Update existing ticket metadata, lifecycle, or placeholders" not in readme
    assert "Preview-first existing-ticket refinement via `ticket_workflow.py`" not in readme

    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized_handbook = _normalize_whitespace(handbook).lower()
    assert "metadata/refinement updates" not in normalized_handbook
    assert "lifecycle, metadata, and placeholder refinement" not in normalized_handbook
    assert "existing-ticket lifecycle and frontmatter metadata updates" in normalized_handbook
    assert "future dedicated `ticket_update.py` backend" in normalized_handbook


def test_docs_describe_capture_first_five_skill_surface() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        text = _read_text(path)
        for snippet in (
            "ticket-capture",
            "ticket-find",
            "ticket-update",
            "ticket-review",
            "ticket-doctor",
            "Generic creation through the old broad `ticket` skill is no longer user-facing",
            "Low-confidence captures are allowed when",
            "`refinement_status: needs_refinement`",
            "metadata",
            "not a lifecycle status",
        ):
            assert snippet in text, str(path)


def test_contract_preserves_engine_boundary_for_workflow_runner() -> None:
    text = (PLUGIN_ROOT / "references" / "ticket-contract.md").read_text(encoding="utf-8")
    assert "Workflow runner" in text
    assert "prepare" in text
    assert "execute" in text
    assert "recover" in text
    assert "does not replace the engine interface" in text

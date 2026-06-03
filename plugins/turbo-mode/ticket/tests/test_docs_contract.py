"""Static contract checks for current-facing docs and skill files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from scripts.ticket_target_schema import (
    TARGET_CANDIDATE_ACTIONS,
    TARGET_FRONTMATTER_FIELDS,
    TARGET_PRIORITIES,
    TARGET_SECTIONS_REQUIRED,
    TARGET_STATUSES,
    validate_target_ticket_file,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[2]
PR22_REPAIR_CLOSEOUT = (
    REPO_ROOT
    / "docs"
    / "superpowers"
    / "closeouts"
    / "2026-05-28-ticket-runtime-first-autonomy-pr22-review-repair.md"
)
ENGINE_RUNNER = PLUGIN_ROOT / "scripts" / "ticket_engine_runner.py"
TICKET_PAYLOADS = PLUGIN_ROOT / "scripts" / "ticket_payloads.py"
CAPTURE_SKILL = PLUGIN_ROOT / "skills" / "capture-ticket" / "SKILL.md"
FIND_SKILL = PLUGIN_ROOT / "skills" / "read-ticket" / "SKILL.md"
UPDATE_SKILL = PLUGIN_ROOT / "skills" / "update-ticket" / "SKILL.md"
REVIEW_SKILL = PLUGIN_ROOT / "skills" / "ticket-backlog-triage" / "SKILL.md"
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
MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CURRENT_FACING_DOCS = SKILL_FILES + [
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
]
CORE_AUTHORITY_DOCS = (
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
)
TARGET_CANDIDATE_FIELDS = (
    "action",
    "ticket_id",
    "target.fields",
    "target.sections",
    "proposed_change",
    "expected_ticket_fingerprint",
    "evidence_summary",
)
TARGET_RESULT_STATES = ("ok", "blocked", "needs_discussion", "invalid_state", "no_change")
OLD_MUTATION_SURFACE_TERMS = (
    "preview-first prepare/execute",
    "ticket_capture.py prepare",
    "ticket_capture.py execute",
    "ticket_update.py prepare",
    "ticket_update.py execute",
    "four-stage",
    "classify`/`plan`/`preflight`/`execute",
)
OLD_SCHEMA_TERMS = (
    "blocked status",
    "`blocked` status",
    "`blocks` reverse",
    "`component`",
    "`refinement_status`",
    "`acceptance_criteria`",
    "`capture_confidence`",
)
GIT_BRANCH_BOOKKEEPING_TERMS = (
    "`ticket_change_scope`",
    "`commit_disposition`",
    "`commit_hash`",
    "`commit_reason`",
    "`commit_dispositions`",
    "commit coordination",
    "commit_recorded",
    "commit_bundled_with_work",
    "commit_deferred",
)
NO_FLAG_LAUNCHER_RE = re.compile(r"python3\s+(?!-B\b)<[^>]+>/scripts/[^\s`]+")
COUNTED_TESTS_RE = re.compile(r"\b\d+\s+tests?\b")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _section(text: str, start: str, end: str | None = None) -> str:
    assert start in text
    body = text.split(start, maxsplit=1)[1]
    return body if end is None else body.split(end, maxsplit=1)[0]


def _target_sections(text: str) -> str:
    sections = []
    for heading in (
        "## Authority Boundary",
        "## Target Post-Cutover Ticket Shape",
        "## Target Candidate Mutation Contract",
        "## Target Result Envelope",
        "## Target Change History Grammar",
    ):
        sections.append(_section(text, heading, "\n## "))
    return "\n".join(sections)


def _deprecated_or_diagnostic_sections(text: str) -> str:
    sections = []
    for heading in (
        "## Deprecated Source Drift",
        "## Legacy Cutover Input",
        "## Historical Changelog",
        "## Maintenance And Diagnostics",
    ):
        if heading in text:
            sections.append(_section(text, heading, "\n## "))
    return "\n".join(sections)


def _assert_authority_boundary(text: str) -> None:
    boundary = _section(text, "## Authority Boundary", "\n## ")
    normalized = _normalize_whitespace(boundary)
    assert "ADR 0006" in normalized
    assert "May 30 control doc" in normalized
    assert "not runtime proof" in normalized or "not installed-runtime proof" in normalized
    assert "does not perform cutover inventory" in normalized


def _assert_target_candidate_contract(text: str) -> None:
    section = _section(text, "## Target Candidate Mutation Contract", "\n## ")
    normalized = _normalize_whitespace(section)
    for field in TARGET_CANDIDATE_FIELDS:
        assert f"`{field}`" in section or field in section
    assert "non-create writes require an expected ticket fingerprint" in normalized
    assert "Ticket computes candidate identity" in normalized
    assert "callers do not supply authoritative identity" in normalized
    assert "Unknown fields are invalid" in normalized


def _assert_target_result_envelope(text: str) -> None:
    section = _section(text, "## Target Result Envelope", "\n## ")
    for state in TARGET_RESULT_STATES:
        assert f"`{state}`" in section
    normalized = _normalize_whitespace(section).lower()
    assert "error code taxonomy" not in normalized
    assert "recovery hint taxonomy" not in normalized


def _assert_target_change_history(text: str) -> None:
    section = _section(text, "## Target Change History Grammar", "\n## ")
    normalized = _normalize_whitespace(section)
    assert "- <timestamp> | <actor> | <reason>" in section
    assert "Corrects: <reference>" in section
    assert "actor" in normalized
    assert "not a workflow label" in normalized
    for old_label in ("auto-create", "auto-update", "discussion-approved"):
        assert old_label not in section


def _json_code_blocks(text: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for match in re.finditer(r"```json\n(.*?)\n```", text, re.DOTALL):
        parsed = json.loads(match.group(1))
        assert isinstance(parsed, dict)
        blocks.append(parsed)
    return blocks


def test_readme_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "README.md")

    _assert_authority_boundary(text)
    _assert_target_candidate_contract(text)
    target = _target_sections(text)
    for term in OLD_MUTATION_SURFACE_TERMS:
        assert term not in target
    assert "`capture`, `update`, and `ingest`" not in target


def test_handbook_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")

    _assert_authority_boundary(text)
    _assert_target_candidate_contract(text)
    target = _target_sections(text)
    for term in OLD_MUTATION_SURFACE_TERMS:
        assert term not in target
    assert "`capture`, `update`, and `ingest`" not in target


def test_contract_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")

    _assert_authority_boundary(text)
    _assert_target_candidate_contract(text)
    target = _target_sections(text)
    for term in OLD_MUTATION_SURFACE_TERMS:
        assert term not in target
    assert "`capture`, `update`, and `ingest`" not in target


def test_readme_ticket_schema_matches_yaml_contract_boundary() -> None:
    text = _read_text(PLUGIN_ROOT / "README.md")
    schema = _section(text, "## Target Post-Cutover Ticket Shape", "\n## ")
    normalized_schema = _normalize_whitespace(schema)

    assert "ID-only filenames" in normalized_schema
    assert "YAML frontmatter" in normalized_schema
    for field in TARGET_FRONTMATTER_FIELDS:
        assert f"`{field}`" in schema
    for status in TARGET_STATUSES:
        assert f"`{status}`" in schema
    for priority in TARGET_PRIORITIES:
        assert f"`{priority}`" in schema
    for section in TARGET_SECTIONS_REQUIRED:
        assert f"`{section}`" in schema
    assert "Unknown frontmatter keys are invalid" in normalized_schema
    assert "`blocked` is not a status" in normalized_schema
    assert "derive reverse `blocks`" in normalized_schema

    for term in OLD_SCHEMA_TERMS:
        assert term not in schema


def test_core_docs_document_target_candidate_mutation_contract() -> None:
    for path in CORE_AUTHORITY_DOCS:
        text = _read_text(path)
        _assert_target_candidate_contract(text)
        target = _target_sections(text)
        assert "target.fields" in target
        assert "target.sections" in target
        assert "expected_ticket_fingerprint" in target
        assert "Unknown fields are invalid" in target


def test_core_docs_do_not_present_git_branch_bookkeeping_as_target_behavior() -> None:
    for path in CORE_AUTHORITY_DOCS:
        text = _read_text(path)
        target = _target_sections(text)
        normalized_target = _normalize_whitespace(target)
        for term in GIT_BRANCH_BOOKKEEPING_TERMS:
            assert term not in normalized_target


def test_core_docs_document_target_result_envelope_states() -> None:
    for path in CORE_AUTHORITY_DOCS:
        _assert_target_result_envelope(_read_text(path))


def test_core_docs_document_target_change_history_grammar() -> None:
    for path in CORE_AUTHORITY_DOCS:
        _assert_target_change_history(_read_text(path))


def test_contract_names_host_facing_autonomy_cli_surface() -> None:
    text = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    target = _target_sections(text)
    allowed = _deprecated_or_diagnostic_sections(text)

    assert "## Deprecated Source Drift" in text or "## Maintenance And Diagnostics" in text
    assert "host-facing autonomy cli" not in _normalize_whitespace(target).lower()
    assert "ordinary high-level user mutation wrappers remain" not in _normalize_whitespace(
        target
    ).lower()
    if "host-facing autonomy CLI" in text:
        assert "host-facing autonomy CLI" in allowed
    _assert_target_candidate_contract(text)


def test_readme_and_handbook_list_all_host_facing_autonomy_commands() -> None:
    commands = (
        "ticket_autonomy.py pause",
        "ticket_autonomy.py recover",
        "ticket_autonomy.py apply-turn",
        "ticket_autonomy.py doctor-ledger",
        "ticket_autonomy.py migrate-change-history",
    )
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        text = _read_text(path)
        target = _target_sections(text)
        maintenance = _deprecated_or_diagnostic_sections(text)
        for command in commands:
            assert f"`{command}`" not in target
            if f"`{command}`" in text:
                assert f"`{command}`" in maintenance


def test_pr22_repair_closeout_records_test4_and_qualified_review_findings() -> None:
    text = _read_text(PR22_REPAIR_CLOSEOUT)
    normalized = _normalize_whitespace(text)

    assert "Development Tenet Test 4" in text
    assert "C14" in text
    assert "undocumented rather than proven absent" in normalized
    assert "C3" in text
    assert "`--resume-paused`" in text
    for finding_id in ("C1", "C2", "C4", "C5", "C6", "C7", "C8", "C11", "C13", "C15"):
        assert finding_id in text


def test_engine_docs_state_runner_is_not_public_mutation_surface() -> None:
    text = _read_text(ENGINE_RUNNER)

    assert "This module is never invoked directly." in text
    assert (
        "The public guarded engine entrypoints are ticket_engine_user.py "
        "and ticket_engine_agent.py."
    ) in text
    assert (
        "Direct engine stages are low-level compatibility, debug, and agent-internal paths."
    ) in text
    assert "not normal user-facing mutation interfaces" in text


def test_docs_describe_direct_agent_execute_gateway_boundary() -> None:
    readme = _read_text(PLUGIN_ROOT / "README.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    direct_agent_boundary = (
        "Direct `ticket_engine_agent.py execute` is not an autonomous mutation route"
    )
    gate_boundary = "fails closed with `gateway_required`"
    gateway_boundary = "runtime-first gateway"
    for text in [readme, handbook, contract]:
        normalized = _normalize_whitespace(text)
        allowed_old_surface = _deprecated_or_diagnostic_sections(text)
        assert direct_agent_boundary not in _target_sections(text)
        if direct_agent_boundary in normalized:
            assert direct_agent_boundary in _normalize_whitespace(allowed_old_surface)
        assert gate_boundary not in _target_sections(text)
        if gate_boundary in normalized:
            assert gate_boundary in _normalize_whitespace(allowed_old_surface)
        assert gateway_boundary not in _target_sections(text)
        _assert_target_change_history(text)
        assert "pending-summary bookkeeping" not in _target_sections(text)
        assert "dangerFullAccess" not in text


def test_contract_separates_core_runtime_and_activation_error_codes() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    target = _target_sections(contract)

    _assert_target_result_envelope(contract)
    assert "Core Engine Error Codes" not in target
    assert "Autonomy Gate Error Codes" not in target
    assert "`need_fields`, `invalid_transition`, `policy_blocked`" not in target
    assert "`setup_required`, `gateway_required`" not in target


def test_response_envelope_docs_point_to_error_code_taxonomy() -> None:
    for path in CORE_AUTHORITY_DOCS:
        text = _read_text(path)
        target = _target_sections(text)
        _assert_target_result_envelope(text)
        assert "error code taxonomy" not in _normalize_whitespace(target).lower()
        assert "core engine error codes" not in _normalize_whitespace(target).lower()
        assert "autonomy gate error codes" not in _normalize_whitespace(target).lower()


def test_contract_documents_current_exit_code_mapping() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    target = _target_sections(contract)

    assert "Exit code" not in target
    if "Exit code" in contract:
        diagnostic = _deprecated_or_diagnostic_sections(contract)
        assert "Exit code" in diagnostic
    assert "Exit code 2 maps to `need_fields` and `invalid_transition`" not in contract


def test_handbook_documents_runtime_proof_env_var_scope() -> None:
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    target = _target_sections(handbook)
    diagnostic = _deprecated_or_diagnostic_sections(handbook)
    normalized = _normalize_whitespace(diagnostic)

    assert "TICKET_RUNTIME_PROOF_PATH" not in target
    assert "`ticket_engine_runner.py execute` may honor `TICKET_RUNTIME_PROOF_PATH`" in normalized
    assert (
        "`TICKET_RUNTIME_ACTIVATION_BOOTSTRAP=1` is an internal activation/test override"
        in normalized
    )
    assert "classify, plan, preflight, and ingest ignore it" in normalized
    assert "At execute and ingest stages, the engine re-validates the trust triple" in normalized


def test_stale_plan_is_only_public_toctou_error_code() -> None:
    for path in (*CORE_AUTHORITY_DOCS, CAPTURE_SKILL, UPDATE_SKILL):
        text = _read_text(path)
        target = _target_sections(text)
        normalized = _normalize_whitespace(target).lower()
        for stale_code in ("stale_plan", "toctou_conflict"):
            assert stale_code not in normalized
        _assert_target_result_envelope(text)


def test_ingest_contract_documents_filename_id_and_indefinite_processed_retention() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    privacy = _read_text(PLUGIN_ROOT / "PRIVACY.md")
    assert "For v1.0, the envelope id is the envelope filename" in contract
    assert "Processed envelopes are retained indefinitely" in contract
    assert "duplicate/replay" in contract
    assert "preserves the incoming envelope" in contract
    assert "Processed envelopes are retained indefinitely" in privacy


def test_project_local_ticket_tmp_payloads_are_ignored() -> None:
    gitignore = _read_text(PLUGIN_ROOT.parents[2] / ".gitignore")

    assert ".codex/ticket-tmp/" in gitignore.splitlines()


def test_docs_contract_imports_source_target_vocabulary() -> None:
    assert TARGET_CANDIDATE_ACTIONS == (
        "create",
        "update",
        "done",
        "wontfix",
        "reopen",
        "correct",
    )


def test_repo_ticket_records_are_target_normalized() -> None:
    tickets_dir = REPO_ROOT / "docs" / "tickets"
    failures = []
    for path in sorted(tickets_dir.glob("*.md")):
        result = validate_target_ticket_file(path)
        if not result.ok:
            failures.append(f"{path}: {result.error}")
    assert failures == []


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


def test_retired_pipeline_guide_is_not_current_source() -> None:
    assert not (PLUGIN_ROOT / "skills" / "ticket" / "references" / "pipeline-guide.md").exists()


def test_task4_split_skill_files_exist() -> None:
    for path in NEW_SKILL_FILES:
        assert path.exists(), str(path)


def test_ticket_capture_skill_frontmatter_matches_task3_contract() -> None:
    text = _read_text(CAPTURE_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "capture-ticket"
    assert frontmatter["allowed-tools"] == ["Bash", "Write", "Read"]
    assert "argument-hint" not in text

    description = frontmatter["description"]
    assert isinstance(description, str)
    for snippet in (
        "track, file, capture, ticket, or remember",
        "bug, feature, follow-up, task, or cleanup item",
        "Do not trigger from casual statements like 'this is a bug'",
        "unless the user also asks to track or file it",
    ):
        assert snippet in description
    assert "temporarily unavailable" in description
    assert "prepare" not in description
    assert "execute" not in description
    assert "preview" not in description


def test_ticket_capture_skill_contains_exact_compact_preview_labels() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    for label in (
        "Capture ticket",
        "Title: <synthesized title>",
        "Problem: <1-2 sentence synthesized problem>",
        "Next action: <single concrete next step>",
        "Confidence: low|medium|high",
        'Duplicate: none | possible T-... "<title>"',
        "Create this ticket? [create / edit / cancel]",
    ):
        assert label not in target
    assert "temporarily unavailable" in target
    assert "preview" not in _normalize_whitespace(target).lower()


def test_ticket_capture_skill_forbids_raw_user_wording() -> None:
    text = _read_text(CAPTURE_SKILL)
    assert "Never store raw user wording" in text
    assert "do not write verbatim transcript text" in text
    assert "raw_user_text" in text
    assert "raw_request" in text
    assert "transcript_excerpt" in text


def test_ticket_capture_skill_requires_explicit_confirmation_before_writing() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    normalized = _normalize_whitespace(target)
    assert "temporarily unavailable" in normalized
    assert "discussion_only" in normalized
    assert "approval tied to the candidate identity" in normalized
    assert "Require explicit `create` confirmation before writing" not in target


def test_ticket_capture_skill_uses_canonical_prepare_and_execute_commands() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    assert "ticket_capture.py prepare" not in target
    assert "ticket_capture.py execute" not in target
    if "ticket_capture.py prepare" in text or "ticket_capture.py execute" in text:
        deprecated = _deprecated_or_diagnostic_sections(text)
        assert "ticket_capture.py prepare" in deprecated
        assert "ticket_capture.py execute" in deprecated


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
    target = _section(text, "## Target Candidate Mutation Contract", "\n## ")
    for field in TARGET_CANDIDATE_FIELDS:
        assert f"`{field}`" in target or field in target
    for old_field in (
        "capture.title",
        "capture.captured_request",
        "capture.capture_confidence",
        "capture.component",
        "capture.acceptance_criteria",
    ):
        assert old_field not in target


def test_ticket_capture_skill_keeps_provenance_hook_owned() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Target Candidate Mutation Contract", "\n## ")
    assert "with a `capture` object only" not in target
    assert "`session_id`" not in target
    assert "`hook_injected`" not in target
    assert "`hook_request_origin`" not in target
    assert "Do not\nwrite `session_id`, `hook_injected`, or `hook_request_origin`" in text
    assert "hook/provenance fields are hook-owned" in text
    assert "injected by the canonical command\npath" not in target
    assert "Top-level fields: `tickets_dir`, `session_id`" not in text


def test_ticket_capture_skill_documents_deterministic_inference_boundaries() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Target Post-Cutover Ticket Shape", "\n## ")
    for priority in TARGET_PRIORITIES:
        assert f"`{priority}`" in target
    assert "`medium`" not in target
    assert "`critical`" not in target
    assert "`component`" not in target
    assert "Do not invent component tags" not in target


def test_ticket_capture_skill_documents_refinement_and_preview_rules() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    normalized = _normalize_whitespace(target).lower()
    assert "temporarily unavailable" in normalized
    assert "refinement_status" not in normalized
    assert "persistent preview" not in normalized
    assert "preview-first" not in normalized


def test_ticket_capture_skill_documents_create_edit_cancel_handling() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    assert "`create`: run execute" not in target
    assert "`edit`: safely update the payload" not in target
    assert "canonical prepare command" not in target
    assert "temporarily unavailable" in target


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


def test_user_facing_ticket_skills_prefer_recovery_hint() -> None:
    for path in [CAPTURE_SKILL, UPDATE_SKILL]:
        text = _normalize_whitespace(_read_text(path))
        assert "`data.recovery_hint`" not in text
        assert "target result envelope" in text
        for state in TARGET_RESULT_STATES:
            assert f"`{state}`" in text
    doctor = _normalize_whitespace(_read_text(DOCTOR_SKILL))
    assert "`data.recovery_hint`" in doctor
    assert "maintenance" in doctor.lower()


def test_contract_documents_recovery_hint_schema_and_codes() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    docs = {
        "ticket-contract.md": contract,
        "HANDBOOK.md": handbook,
    }
    for name, text in docs.items():
        target = _target_sections(text)
        _assert_target_result_envelope(text)
        assert "`data.recovery_hint`" not in target, name
        assert "`retry_preview`" not in target, name
        assert "`cleanup_stale_preview`" not in target, name
        assert "`engine_gate_required`" not in target, name


def test_ticket_capture_skill_owns_creation_without_broad_ticket_skill() -> None:
    text = _read_text(CAPTURE_SKILL)
    target = _section(text, "## Active Create Guidance", "\n## ")
    assert "temporarily unavailable" in target
    assert "ticket_capture.py prepare" not in target
    assert "ticket_capture.py execute" not in target
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
    assert frontmatter["name"] == "read-ticket"
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
        (
            "do not create, update, close, reopen, triage, repair, prioritize, "
            "or answer what to work on next"
        ),
        "use ticket-backlog-triage for backlog health and next-action analysis",
    ):
        assert snippet in description
    assert "ticket_read.py list" in text
    assert "ticket_read.py query" in text
    assert "ticket_read.py check" in text
    assert "ticket_workflow.py" not in text
    assert "ticket_audit.py repair" not in text
    target = _section(text, "## Target Post-Cutover Ticket Shape", "\n## ")
    for status in TARGET_STATUSES:
        assert f"`{status}`" in target
    for priority in TARGET_PRIORITIES:
        assert f"`{priority}`" in target
    assert "`blocked`" not in target
    assert "`critical`" not in target
    assert "`medium`" not in target
    assert "`refinement_status`" not in target


def test_ticket_update_skill_contract_is_preview_first_and_scoped() -> None:
    text = _read_text(UPDATE_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "update-ticket"
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
    ):
        assert snippet in description
    assert "temporarily unavailable" in description
    assert "component" not in description
    assert "acceptance criteria" not in description
    assert "preview" not in description
    target = _section(text, "## Active Update Guidance", "\n## ")
    assert "temporarily unavailable" in target
    assert "Show the returned preview and wait for explicit user confirmation" not in target
    assert "ticket_update.py prepare" not in target
    assert "ticket_update.py execute" not in target
    assert "Refinement: will clear needs-refinement" not in target
    normalized = _normalize_whitespace(text)
    assert "target.fields" in normalized
    assert "target.sections" in normalized
    assert "expected_ticket_fingerprint" in normalized
    assert "evidence_summary" in normalized
    candidate_contract = _section(text, "## Target Candidate Mutation Contract", "\n## ")
    assert "acceptance_criteria" not in candidate_contract
    for block in _json_code_blocks(text):
        assert "action" in block
        assert "target" in block
        assert "proposed_change" in block
    assert "Do not write `session_id`, `hook_injected`, or `hook_request_origin`" in normalized
    assert "canonical hook injects trust fields" in normalized


def test_ticket_update_json_examples_do_not_use_invalid_needs_refinement_tag() -> None:
    text = _read_text(UPDATE_SKILL)
    examples = _json_code_blocks(_section(text, "## Target Candidate Mutation Contract", "\n## "))
    assert examples
    for example in examples:
        target = example.get("target")
        assert isinstance(target, dict)
        assert "fields" in target or "sections" in target
        assert "refinement_status" not in json.dumps(example)
        assert "acceptance_criteria" not in json.dumps(example)
        assert "component" not in json.dumps(example)


def test_ticket_review_skill_contract_is_read_only_and_capture_prompt_only() -> None:
    text = _read_text(REVIEW_SKILL)
    frontmatter = _frontmatter(text)
    assert set(frontmatter) == {"name", "description", "allowed-tools"}
    assert frontmatter["name"] == "ticket-backlog-triage"
    assert frontmatter["allowed-tools"] == ["Bash", "Read"]
    description = frontmatter["description"]
    assert isinstance(description, str)
    assert "Read-only" in description
    assert "may suggest capture prompts but must not write tickets" in description
    assert (
        "Do not use for direct show, list, search, ticket lookup, or close-readiness requests"
        in description
    )
    assert "use read-ticket" in description
    assert "ticket_review.py review" in text
    assert "ticket_review.py audit" in text
    assert "ticket_triage.py dashboard" not in text
    assert "ticket_triage.py audit" not in text
    normalized = _normalize_whitespace(text)
    assert "ADR 0006" in normalized
    assert "May 30 control doc" in normalized
    assert "Backlog triage is read/query/reporting" in normalized
    assert (
        "Persisted `blocked` status and reverse `blocks` edges are not target schema"
        in normalized
    )
    assert "target blockedness derives from `blocked_by`" in normalized
    assert "blocked-chain analysis" not in normalized
    assert "Do not create, update, close, reopen, doctor, or repair tickets" in normalized
    assert "suggest a concrete `capture-ticket` prompt instead of writing the ticket" in normalized


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
    normalized = _normalize_whitespace(text)
    assert "ADR 0006" in normalized
    assert "May 30 control doc" in normalized
    assert "maintenance and diagnostic material only" in normalized
    assert "not normal target ticket mutation authority" in normalized
    assert (
        "Preview, audit logs, activation proof, and cache refresh are not part of "
        "ordinary target capture or update mutation"
        in normalized
    )
    assert "not target preview-mode authority" in normalized
    assert "historical audit artifacts only" in normalized
    assert "ticket_doctor.py diagnose" in text
    assert (
        "ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path <MARKETPLACE_PATH>"
    ) in text
    assert "ticket_doctor.py repair-audit <TICKETS_DIR>" in text
    assert "ticket_doctor.py repair-audit <TICKETS_DIR> --confirm-repair" in text
    assert "ticket_doctor.py clean-stale-payloads <TICKETS_DIR>" in text
    assert (
        "ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads"
    ) in text
    assert "stale `.codex/ticket-tmp/` payloads" in text
    assert "24 hours" in text
    assert "ask before any cleanup mutation" in text
    assert "direct_execute only" in text
    assert "Activation is user-origin only" in text
    assert "Do not run this command as an agent" in text
    assert "a user-owned shell must run it" in text
    assert "`host_policy_blocked`" in text
    assert "`deterministic_driver_unavailable`" in text
    assert "`hook_contract_blocked`" in text
    assert "`engine_gate_required`" in text
    assert "`runtime_readiness_required`" in text
    assert "`proof_invalid`" in text
    assert "`stale_proof`" in text
    assert "cache-installed" in text
    assert "staging only, not the proof target" in text
    assert "ticket_audit.py repair <TICKETS_DIR>" not in text
    assert "ask before any mutation" in text


def test_ticket_payloads_does_not_expose_boolean_security_gate_helpers() -> None:
    text = _read_text(TICKET_PAYLOADS)

    assert "def ticket_tmp_dir(" not in text
    assert "def is_ticket_tmp_payload(" not in text


def test_doctor_docs_describe_confirmed_stale_payload_cleanup() -> None:
    readme = _read_text(PLUGIN_ROOT / "README.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    skill = _read_text(DOCTOR_SKILL)
    for text in [readme, handbook, skill]:
        normalized = _normalize_whitespace(text)
        assert "reports stale `.codex/ticket-tmp/` payloads" in normalized
        assert "older than 24 hours; diagnose reports stale" not in normalized
        assert "24 hours" in text
        assert "`ticket_doctor.py clean-stale-payloads <TICKETS_DIR>`" in text
        assert "`--confirm-clean-stale-payloads`" in text


def test_handbook_documents_runtime_activation_operator_flow() -> None:
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    target = _target_sections(handbook)
    diagnostics = _deprecated_or_diagnostic_sections(handbook)
    normalized = _normalize_whitespace(diagnostics)

    assert "`scripts/ticket_doctor.py` | User | Explicit-only diagnostics" in handbook
    assert "runtime activation" in handbook
    assert (
        "uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py activate-runtime "
        "<TICKETS_DIR> --marketplace-path <MARKETPLACE_PATH>"
    ) in handbook
    assert "`gateway_required`" in handbook
    assert "ticket_triage.py doctor" in handbook
    assert "backend/diagnostic path" in handbook
    assert "not the preferred user-facing doctor entrypoint" in handbook
    assert (
        "`ticket_doctor.py diagnose` reports source/cache parity, runtime-proof status"
        in normalized
    )
    assert "installed Ticket runtime" in normalized
    assert "`in_progress`" in normalized
    assert "`done` requires an Acceptance Criteria section" not in target
    assert "open`, `in_progress`, or `blocked`" not in target


def test_handbook_documents_ticket_triage_doctor_runtime_probe_output() -> None:
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized = _normalize_whitespace(handbook)

    assert (
        "uv run python -B <PLUGIN_ROOT>/scripts/ticket_triage.py doctor <tickets_dir> "
        "--plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT> [--runtime-probe-output <path>]"
    ) in handbook
    assert "undefined behavior" not in handbook
    assert "`ticket_engine_activation_smoke.py`" in handbook
    assert "private activation-smoke entrypoint" in normalized


def test_readme_and_handbook_do_not_describe_guard_as_fail_open() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        text = _read_text(path)
        normalized = _normalize_whitespace(text)
        assert "fail-open" not in normalized
        assert "fail closed" in normalized or "fail-closed" in normalized


def test_current_docs_describe_audit_as_historical_only() -> None:
    docs = (
        PLUGIN_ROOT / "README.md",
        PLUGIN_ROOT / "HANDBOOK.md",
        PLUGIN_ROOT / "references" / "ticket-contract.md",
    )
    forbidden_current_guidance = (
        "autonomy_mode: auto_audit",
        "Set `autonomy_mode: auto_audit`",
        "requires auto_audit",
        "requires `auto_audit`",
        "created automatically on the first agent mutation",
        "Append-only audit trail",
        "full audit trail",
        "After a successful agent mutation (requires auto_audit mode)",
    )

    for path in docs:
        text = _read_text(path)
        target = _target_sections(text)
        _assert_target_change_history(text)
        assert ".audit" not in target
        if ".audit" in text:
            diagnostic = _deprecated_or_diagnostic_sections(text)
            assert "historical" in _normalize_whitespace(diagnostic).lower()
        for phrase in forbidden_current_guidance:
            assert phrase not in text, f"{path} still contains active audit guidance: {phrase}"


def test_handbook_documents_direct_agent_execute_gateway_requirement() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized = _normalize_whitespace(text)
    target = _target_sections(text)

    assert "Direct `ticket_engine_agent.py execute`" not in target
    assert "`gateway_required`" not in target
    if "Direct `ticket_engine_agent.py execute`" in normalized:
        allowed = _normalize_whitespace(_deprecated_or_diagnostic_sections(text))
        assert "Direct `ticket_engine_agent.py execute`" in allowed
        assert "`gateway_required`" in allowed


def test_changelog_announces_activate_runtime_subcommand() -> None:
    text = _read_text(PLUGIN_ROOT / "CHANGELOG.md")
    unreleased = text.split("## 1.4.0", maxsplit=1)[0]

    assert "`ticket_doctor.py activate-runtime`" in unreleased
    for skill_name in (
        "capture-ticket",
        "read-ticket",
        "update-ticket",
        "ticket-backlog-triage",
        "ticket-doctor",
    ):
        assert f"`{skill_name}`" in unreleased
    for old_skill_name in (
        "ticket-capture",
        "ticket-find",
        "ticket-update",
        "ticket-review",
    ):
        assert f"`{old_skill_name}`" not in unreleased


def test_claude_instructions_reference_current_turbo_mode_source_roots() -> None:
    text = _read_text(REPO_ROOT / ".claude" / "CLAUDE.md")

    assert "plugins/turbo-mode/ticket/1.4.0" not in text
    assert "plugins/turbo-mode/handoff/1.6.0" not in text
    assert "`plugins/turbo-mode/ticket/` - Ticket plugin source." in text
    assert "`plugins/turbo-mode/handoff/` - Handoff plugin source." in text
    assert "uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ..." in text
    assert "python3 -B <PLUGIN_ROOT>/scripts/<script>.py ..." not in text
    assert "uv run --directory plugins/turbo-mode/ticket pytest -q" in text
    assert "uv run --directory plugins/turbo-mode/handoff pytest -q" in text


def test_repo_agents_instructions_reference_ticket_public_launcher() -> None:
    text = _read_text(REPO_ROOT / "AGENTS.md")

    assert "uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ..." in text
    assert "python3 -B <PLUGIN_ROOT>/scripts/<script>.py ..." not in text


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
            assert "uv run python -B <PLUGIN_ROOT>/scripts/" in text, str(path)


def test_launcher_docs_mark_python3_as_legacy_compatibility() -> None:
    for path in (
        PLUGIN_ROOT / "README.md",
        PLUGIN_ROOT / "HANDBOOK.md",
        PLUGIN_ROOT / "references" / "ticket-contract.md",
    ):
        normalized = _normalize_whitespace(_read_text(path))
        assert "uv run python -B" in normalized, str(path)
        assert "legacy compatibility" in normalized, str(path)


def test_current_facing_docs_do_not_keep_no_flag_plugin_launchers() -> None:
    for path in CURRENT_FACING_DOCS:
        assert not NO_FLAG_LAUNCHER_RE.search(_read_text(path)), str(path)


def test_handbook_shell_metacharacter_list_matches_guard_regex() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "Rejects shell metacharacters: `|`, `;`, `` ` ``, `$`, `&`, `<`, `>`, newlines" in text
    assert "`(`, `)`" not in text


def test_handbook_does_not_advertise_stale_test_count_or_version_footer() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "596 passed" not in text
    assert "Plugin v1.2.0" not in text


def test_readme_and_handbook_do_not_advertise_counted_test_inventory() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        assert not COUNTED_TESTS_RE.search(_read_text(path)), str(path)


def test_update_skill_uses_focused_update_backend_as_mutation_path() -> None:
    text = _read_text(UPDATE_SKILL)
    active = _section(text, "## Active Update Guidance", "\n## ")
    assert "temporarily unavailable" in active
    assert "ticket_update.py prepare" not in active
    assert "ticket_update.py execute" not in active
    assert "<PLUGIN_ROOT>/scripts/ticket_update.py prepare <PAYLOAD_PATH>" not in active
    assert "preview" not in _normalize_whitespace(active).lower()
    assert "Refinement: will clear needs-refinement" not in active
    assert "rerun `prepare` for the same `PAYLOAD_PATH`" not in _normalize_whitespace(active)


def test_split_skills_document_check_review_and_doctor_surfaces() -> None:
    find_text = _read_text(FIND_SKILL)
    review_text = _read_text(REVIEW_SKILL)
    doctor_text = _read_text(DOCTOR_SKILL)
    assert "ticket_read.py check" in find_text
    assert "ticket_review.py review" in review_text
    assert "ticket_review.py audit" in review_text
    assert "ticket_triage.py dashboard" not in review_text
    assert "ticket_triage.py audit" not in review_text
    assert "ticket_triage.py doctor" not in review_text
    assert "ticket_triage.py doctor" not in doctor_text
    assert "ticket_doctor.py diagnose" in doctor_text
    assert "ticket_doctor.py activate-runtime" in doctor_text
    assert "ticket_doctor.py repair-audit" in doctor_text
    assert "<CACHE_ROOT>" in doctor_text
    assert "/Users/jp/.codex/plugins/cache/" not in find_text
    assert "/Users/jp/.codex/plugins/cache/" not in review_text
    assert "/Users/jp/.codex/plugins/cache/" not in doctor_text


def test_readme_documents_ticket_ux_commands() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    target = _target_sections(text)
    maintenance = _section(text, "## Maintenance And Diagnostics", "\n## ")
    assert "ticket_capture.py` | `prepare <payload_file>` / `execute <payload_file>`" not in target
    assert "ticket_update.py` | `prepare <payload_file>` / `execute <payload_file>`" not in target
    assert (
        "ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]`"
        in maintenance
    )
    assert (
        "ticket_doctor.py` | `diagnose <tickets_dir> --plugin-root <plugin_root> "
        "--cache-root <cache_root> [--runtime-probe-output <path>]`"
    ) in maintenance
    assert (
        "ticket_doctor.py` | `activate-runtime <tickets_dir> --marketplace-path <marketplace_path>`"
    ) in maintenance
    assert "ticket_doctor.py` | `repair-audit <tickets_dir> [--confirm-repair]`" in maintenance
    assert (
        "ticket_triage.py` | `doctor <tickets_dir> --plugin-root <plugin_root> "
        "--cache-root <cache_root> [--runtime-probe-output <path>]`"
    ) in maintenance
    assert "ticket_audit.py` | `repair <tickets_dir> [--fix | --dry-run]`" in maintenance
    assert "ticket_workflow.py" not in target
    assert "ticket_read.py` | `check" in text
    assert "| doctor/repair | explicit maintenance request | `ticket_doctor.py diagnose`" in text
    assert "**Maintenance entrypoints:**" in text
    assert "skills/ticket/references/pipeline-guide.md" not in text


def test_readme_classifies_activate_runtime_as_maintenance_not_read_only() -> None:
    text = _read_text(PLUGIN_ROOT / "README.md")
    read_only = text.split("**Read-only entrypoints:**", maxsplit=1)[1].split(
        "**Maintenance entrypoints:**",
        maxsplit=1,
    )[0]
    maintenance = text.split("**Maintenance entrypoints:**", maxsplit=1)[1]

    assert "activate-runtime <tickets_dir> --marketplace-path <marketplace_path>" not in read_only
    assert "activate-runtime <tickets_dir> --marketplace-path <marketplace_path>" in maintenance


def test_readme_and_handbook_use_source_authority_installed_boundary() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        text = _read_text(path)
        normalized = _normalize_whitespace(text)
        assert "~/.codex/plugins/ticket" not in text
        assert "source-authority" in text
        assert "Source edits here do not prove installed Codex behavior" in normalized
        assert "cache-refresh or runtime-proof lane" in normalized
        assert "cache-installed runtime authority" in normalized
        assert "staging only, not the proof target" in normalized


def test_handbook_surface_matches_focused_backend() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    target = _target_sections(text)
    normalized = _normalize_whitespace(target)
    assert "source, defer, capture metadata" not in normalized
    assert "lifecycle, priority, tags, blockers, component, related paths" not in normalized
    assert "focused refinement fields" not in normalized
    _assert_target_candidate_contract(text)


def test_handbook_smoke_uses_capture_preview_with_workspace_payload() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    target = _target_sections(text)
    assert "/tmp/test_payload.json" not in text
    assert "ticket_engine_user.py classify" not in target
    assert (
        "ticket_capture.py prepare <PROJECT_ROOT>/.codex/ticket-tmp/capture-smoke.json"
        not in target
    )
    assert "do not run execute unless you intend to create the ticket" not in target
    _assert_target_candidate_contract(text)


def test_manifest_documents_required_interface_urls() -> None:
    manifest = json.loads(_read_text(MANIFEST))
    interface = manifest["interface"]
    expected_urls = {
        "websiteURL": (
            "https://github.com/jpsweeney97/codex-tool-dev/tree/main/plugins/turbo-mode/ticket"
        ),
        "privacyPolicyURL": (
            "https://github.com/jpsweeney97/codex-tool-dev/blob/main/"
            "plugins/turbo-mode/ticket/PRIVACY.md"
        ),
        "termsOfServiceURL": (
            "https://github.com/jpsweeney97/codex-tool-dev/blob/main/"
            "plugins/turbo-mode/ticket/TERMS.md"
        ),
    }
    for key, expected_url in expected_urls.items():
        assert interface[key] == expected_url

    for key in ("privacyPolicyURL", "termsOfServiceURL"):
        url_path = Path(urlparse(interface[key]).path)
        assert url_path.parts[-4:-1] == ("plugins", "turbo-mode", "ticket")
        assert (PLUGIN_ROOT / url_path.name).exists(), key


def test_plugin_default_prompts_are_capture_first() -> None:
    text = _read_text(MANIFEST)
    assert '"Track this follow-up"' not in text
    assert '"Check ticket capture availability"' in text
    assert '"Find open ticket work"' in text
    assert '"Review ticket backlog health"' in text
    assert '"Create a ticket for this work"' not in text
    assert '"Update this ticket"' not in text
    assert '"Close this ticket"' not in text
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
        terms = set(re.findall(r"[a-z]+(?: repair)?", lowered))
        assert not old_surface_terms.issubset(terms), str(path)
        assert "create, update, close, reopen, list, query" not in lowered
        assert "full crud" not in lowered


def test_task4_docs_do_not_overclaim_current_placeholder_refinement() -> None:
    update_description = _frontmatter(_read_text(UPDATE_SKILL))["description"]
    assert isinstance(update_description, str)
    assert (
        "replace placeholder problem, next action, or acceptance criteria"
        not in update_description
    )
    assert "temporarily unavailable" in update_description

    update_text = _normalize_whitespace(_read_text(UPDATE_SKILL))
    assert "Only the focused refinement fields `problem`, `next_action`, and" not in update_text
    assert "`acceptance_criteria` may change ticket body sections" not in update_text
    active_update = _section(_read_text(UPDATE_SKILL), "## Active Update Guidance", "\n## ")
    assert "ticket_update.py prepare" not in active_update

    readme = _read_text(PLUGIN_ROOT / "README.md")
    assert "placeholder-field updates through preview-first workflow commands" not in readme
    assert "Update existing ticket metadata, lifecycle, or placeholders" not in readme
    assert "Preview-first existing-ticket refinement via `ticket_workflow.py`" not in readme

    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized_handbook = _normalize_whitespace(handbook).lower()
    assert "lifecycle, metadata, and placeholder refinement" not in normalized_handbook
    assert "future dedicated `ticket_update.py` backend" not in normalized_handbook
    assert "no dedicated `ticket_update.py` backend exists yet" not in normalized_handbook
    assert "ticket_update.py prepare" not in _target_sections(handbook)
    assert "ticket_update.py execute" not in _target_sections(handbook)
    assert "preferred way to create or mutate tickets" not in normalized_handbook
    assert "`ticket_workflow.py` is a compatibility/debug runner" not in _normalize_whitespace(
        _target_sections(handbook)
    )
    update_runbook = _section(handbook, "### `ticket_update.py`", "\n### ")
    assert "deprecated" in update_runbook.lower() or "unavailable" in update_runbook.lower()
    assert "performs the write after user confirmation" not in update_runbook


def test_current_facing_docs_do_not_keep_old_active_product_sections() -> None:
    forbidden_active_phrases = (
        "Ticket has exactly three supported high-level mutation surfaces",
        "Capture new tickets from natural language after preview confirmation",
        "Preview-first updates via `ticket_update.py prepare` and `execute`",
        "Every mutation traverses all four stages in sequence",
        "Tickets use fenced YAML blocks",
        "Runtime-first modes: `discussion_only`, `preview`, and `agent_primary`",
        "All mutations display a confirmation prompt",
    )
    for path in CORE_AUTHORITY_DOCS:
        text = _read_text(path)
        for phrase in forbidden_active_phrases:
            assert phrase not in text, f"{path} still has old active product wording"


def test_docs_describe_capture_first_five_skill_surface() -> None:
    for path in (PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "HANDBOOK.md"):
        text = _read_text(path)
        for snippet in (
            "capture-ticket",
            "read-ticket",
            "update-ticket",
            "ticket-backlog-triage",
            "ticket-doctor",
            "Generic creation through the old broad `ticket` skill is no longer user-facing",
        ):
            assert snippet in text, str(path)
        target = _target_sections(text)
        assert "Low-confidence captures are allowed when" not in target
        assert "`refinement_status: needs_refinement`" not in target
        assert "capture-first five-skill" not in _normalize_whitespace(target).lower()


def test_contract_preserves_engine_boundary_for_workflow_runner() -> None:
    text = (PLUGIN_ROOT / "references" / "ticket-contract.md").read_text(encoding="utf-8")
    target = _target_sections(text)
    assert "Workflow runner" not in target
    assert "prepare" not in target
    assert "execute" not in target
    if "Workflow runner" in text:
        assert "Workflow runner" in _deprecated_or_diagnostic_sections(text)

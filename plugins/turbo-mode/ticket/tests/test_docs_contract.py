"""Static contract checks for current-facing docs and skill files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ENGINE_RUNNER = PLUGIN_ROOT / "scripts" / "ticket_engine_runner.py"
TICKET_PAYLOADS = PLUGIN_ROOT / "scripts" / "ticket_payloads.py"
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


def test_readme_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "README.md")

    supported_surfaces = (
        "Ticket has exactly three supported high-level mutation surfaces: "
        "`capture`, `update`, and `ingest`."
    )
    ingest_surface = (
        "`ingest`: `ticket_engine_user.py ingest <payload_file>` or "
        "`ticket_engine_agent.py ingest <payload_file>`"
    )
    assert supported_surfaces in text
    assert "`capture` and `update` use their preview-first prepare/execute wrappers." in text
    assert ingest_surface in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "They are not normal user-facing mutation interfaces" in text
    assert "`ticket_workflow.py` is a compatibility/debug runner" in text
    assert "`ticket_workflow.py` is not a supported user-facing mutation surface" in text


def test_handbook_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")

    supported_surfaces = (
        "Ticket has exactly three supported high-level mutation surfaces: "
        "`capture`, `update`, and `ingest`."
    )
    assert supported_surfaces in text
    assert "`ingest` uses the guarded engine entrypoints" in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "`ticket_workflow.py` is a compatibility/debug runner" in text
    assert "ticket_workflow.py is a compatibility/debug runner, not" not in text
    assert "not normal user-facing mutation interfaces" in text


def test_contract_states_supported_high_level_mutation_surfaces() -> None:
    text = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")

    supported_surfaces = (
        "Ticket has exactly three supported high-level mutation surfaces: "
        "`capture`, `update`, and `ingest`."
    )
    assert supported_surfaces in text
    assert "`ingest` uses the guarded engine entrypoints" in text
    assert "Direct engine `classify`/`plan`/`preflight`/`execute`" in text
    assert "must not be documented as the preferred way to create or mutate tickets" in text


def test_engine_docs_state_runner_is_not_public_mutation_surface() -> None:
    text = _read_text(ENGINE_RUNNER)

    assert "This module is never invoked directly." in text
    assert (
        "The public guarded engine entrypoints are ticket_engine_user.py "
        "and ticket_engine_agent.py."
    ) in text
    assert (
        "Direct engine stages are low-level compatibility, debug, "
        "and agent-internal paths."
    ) in text
    assert "not normal user-facing mutation interfaces" in text


def test_docs_describe_direct_execute_activation_v1_boundary() -> None:
    readme = _read_text(PLUGIN_ROOT / "README.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    certified_lane = "Activation V1 certifies only `ticket_engine_agent.py execute`."
    trust_boundary = (
        "Activation V1 proves installed hook-mediated direct-execute wiring, "
        "not host-owned or spawned-agent identity."
    )
    metadata_boundary = (
        "`hook_request_origin` is hook-observed provenance metadata on the current host "
        'and may still be reported as `"user"` for the certified direct-execute lane.'
    )
    scope_boundary = (
        "`capture`, `update`, and `ticket_workflow.py` remain outside the activation proof "
        "scope and require a separate follow-up before widening certification."
    )
    diagnostics_boundary = "`dangerFullAccess` runs and prompt-driven smokes are diagnostics only."
    corroboration_boundary = (
        "AgentControl child smoke, when captured, is same-membrane corroboration only "
        "and not identity proof."
    )
    gate_boundary = (
        "Normal agent direct execute fails with `runtime_readiness_required` when the "
        "runtime proof is missing, stale, or mismatched."
    )
    for text in [readme, handbook, contract]:
        normalized = _normalize_whitespace(text)
        assert certified_lane in normalized
        assert trust_boundary in normalized
        assert metadata_boundary in normalized
        assert scope_boundary in normalized
        assert diagnostics_boundary in normalized
        assert corroboration_boundary in normalized
        assert gate_boundary in normalized


def test_stale_plan_is_only_public_toctou_error_code() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read_text(path)
        normalized = _normalize_whitespace(text).lower()
        assert "error_code: toctou_conflict" not in normalized
        assert "error code `toctou_conflict`" not in normalized
        assert "blocked with a `toctou_conflict` error" not in normalized
        assert "| `toctou_conflict`" not in text
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    assert "`stale_plan`" in contract
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "`toctou_conflict` is descriptive prose only, not a public error code." in handbook


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
    assert not (
        PLUGIN_ROOT / "skills" / "ticket" / "references" / "pipeline-guide.md"
    ).exists()


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
        "uv run python -B <PLUGIN_ROOT>/scripts/ticket_capture.py prepare <PAYLOAD_PATH>"
        in text
    )
    assert (
        "uv run python -B <PLUGIN_ROOT>/scripts/ticket_capture.py execute <PAYLOAD_PATH>"
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


def test_user_facing_ticket_skills_prefer_recovery_hint() -> None:
    for path in [CAPTURE_SKILL, UPDATE_SKILL, DOCTOR_SKILL]:
        text = _normalize_whitespace(_read_text(path))
        assert "`data.recovery_hint`" in text
        assert "show the recovery summary and next step" in text
        assert (
            "Do not expose payload paths, envelope paths, canonical command repair, "
            "raw temp/workspace paths, or hook/provenance fields"
        ) in text


def test_contract_documents_recovery_hint_schema_and_codes() -> None:
    contract = _read_text(PLUGIN_ROOT / "references" / "ticket-contract.md")
    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    docs = {
        "ticket-contract.md": contract,
        "HANDBOOK.md": handbook,
    }
    for name, text in docs.items():
        assert "`data.recovery_hint`" in text, name
        for code in [
            "stale_plan",
            "trust_setup",
            "retry_preview",
            "cleanup_stale_preview",
            "policy_blocked",
            "preflight_failed",
        ]:
            assert f"`{code}`" in text, name
        assert "safe to show directly to a human user" in text, name
        assert "Ingest stdout is a machine-readable JSON envelope" in text, name
        assert "allowlisted projection" in text, name


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
        (
            "do not create, update, close, reopen, triage, repair, prioritize, "
            "or answer what to work on next"
        ),
        "use ticket-review for backlog health and next-action analysis",
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
        "replace placeholder problem, next action, or acceptance criteria",
        "Requires preview before writing",
    ):
        assert snippet in description
    assert "Do not perform arbitrary body-section editing in v1" in text
    assert "Show the returned preview and wait for explicit user confirmation" in text
    assert "ticket_update.py prepare" in text
    assert "ticket_update.py execute" in text
    assert "Refinement: will clear needs-refinement" in text
    normalized = _normalize_whitespace(text)
    assert "existing-ticket lifecycle, metadata, and focused refinement updates" in normalized
    assert (
        "Only the focused refinement fields `problem`, `next_action`, and "
        "`acceptance_criteria` may change ticket body sections"
    ) in normalized
    assert "Reject requests to replace unrelated sections" in normalized
    assert "Priority-only or tag-only updates keep `refinement_status`" in normalized
    assert '"tickets_dir": "docs/tickets"' in text
    assert '"update": {' in text
    assert '"status": "done"' in text
    assert '"status": "open"' in text
    assert '"ticket_id": "T-20260518-01"' in text
    assert "acceptance_criteria" in text
    for block in _json_code_blocks(text):
        assert "action" not in block
        assert "args" not in block
        assert "fields" not in block
    assert "Do not write `session_id`, `hook_injected`, or `hook_request_origin`" in normalized
    assert "canonical hook injects trust fields" in normalized


def test_ticket_update_json_examples_do_not_use_invalid_needs_refinement_tag() -> None:
    text = _read_text(UPDATE_SKILL)
    examples = _json_code_blocks(text)
    assert examples
    for example in examples:
        update = example.get("update")
        assert isinstance(update, dict)
        tags = update.get("tags")
        if isinstance(tags, list) and "needs-refinement" in tags:
            problem = update.get("problem")
            next_action = update.get("next_action")
            criteria = update.get("acceptance_criteria")
            assert isinstance(problem, str) and problem
            assert isinstance(next_action, str) and next_action
            assert isinstance(criteria, list) and criteria


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
    assert (
        "Do not use for direct show, list, search, ticket lookup, or close-readiness requests"
        in description
    )
    assert "use ticket-find" in description
    assert "ticket_review.py review" in text
    assert "ticket_review.py audit" in text
    assert "ticket_triage.py dashboard" not in text
    assert "ticket_triage.py audit" not in text
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
    assert "ticket_doctor.py diagnose" in text
    assert (
        "ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path "
        "<MARKETPLACE_PATH>"
    ) in text
    assert "ticket_doctor.py repair-audit <TICKETS_DIR>" in text
    assert "ticket_doctor.py repair-audit <TICKETS_DIR> --confirm-repair" in text
    assert "ticket_doctor.py clean-stale-payloads <TICKETS_DIR>" in text
    assert (
        "ticket_doctor.py clean-stale-payloads <TICKETS_DIR> "
        "--confirm-clean-stale-payloads"
    ) in text
    assert "stale `.codex/ticket-tmp/` payloads" in text
    assert "24 hours" in text
    assert "ask before any cleanup mutation" in text
    assert "direct_execute only" in text
    assert "`host_policy_blocked`" in text
    assert "`deterministic_driver_unavailable`" in text
    assert "`hook_contract_blocked`" in text
    assert "`engine_gate_required`" in text
    assert "`runtime_readiness_required`" in text
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


def test_update_skill_uses_focused_update_backend_as_mutation_path() -> None:
    text = _read_text(UPDATE_SKILL)
    assert "ticket_update.py prepare" in text
    assert "ticket_update.py execute" in text
    assert "<PLUGIN_ROOT>/scripts/ticket_update.py prepare <PAYLOAD_PATH>" in text
    assert "<PROJECT_ROOT>/.codex/ticket-tmp/" in text
    assert "absolute path under" in text
    assert "preview" in text
    assert "Refinement: will clear needs-refinement" in text
    normalized = _normalize_whitespace(text)
    assert "rerun `prepare` for the same `PAYLOAD_PATH`" in normalized
    assert "ticket_update.py" in text


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
    assert "ticket_capture.py` | `prepare <payload_file>` / `execute <payload_file>`" in text
    assert "ticket_update.py` | `prepare <payload_file>` / `execute <payload_file>`" in text
    assert "ticket_review.py` | `review <tickets_dir>` / `audit <tickets_dir> [--days N]`" in text
    assert (
        "ticket_doctor.py` | `diagnose <tickets_dir> --plugin-root <plugin_root> "
        "--cache-root <cache_root>`"
    ) in text
    assert (
        "ticket_doctor.py` | `activate-runtime <tickets_dir> --marketplace-path "
        "<marketplace_path>`"
    ) in text
    assert "ticket_doctor.py` | `repair-audit <tickets_dir> [--confirm-repair]`" in text
    assert "ticket_workflow.py" in text
    assert "Internal/debugging legacy workflow runner" in text
    assert "ticket_read.py` | `check" in text
    assert "| doctor/repair | explicit maintenance request | `ticket_doctor.py diagnose`" in text
    assert "skills/ticket/references/pipeline-guide.md" not in text


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


def test_handbook_update_surface_matches_focused_backend() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized = _normalize_whitespace(text)
    assert "source, defer, capture metadata" not in normalized
    assert "Source, defer, and capture provenance metadata are not supported" in normalized
    assert "lifecycle, priority, tags, blockers, component, related paths" in normalized
    assert "focused refinement fields" in normalized


def test_handbook_smoke_uses_capture_preview_with_workspace_payload() -> None:
    text = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    assert "/tmp/test_payload.json" not in text
    assert "ticket_engine_user.py classify" not in text
    assert "ticket_capture.py prepare <PROJECT_ROOT>/.codex/ticket-tmp/capture-smoke.json" in text
    assert "mkdir -p <PROJECT_ROOT>/.codex/ticket-tmp" in text
    assert "do not run execute unless you intend to create the ticket" in text


def test_manifest_documents_required_interface_urls() -> None:
    manifest = json.loads(_read_text(MANIFEST))
    interface = manifest["interface"]
    expected_urls = {
        "websiteURL": (
            "https://github.com/jpsweeney97/codex-tool-dev/tree/main/"
            "plugins/turbo-mode/ticket"
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
        terms = set(re.findall(r"[a-z]+(?: repair)?", lowered))
        assert not old_surface_terms.issubset(terms), str(path)
        assert "create, update, close, reopen, list, query" not in lowered
        assert "full crud" not in lowered


def test_task4_docs_do_not_overclaim_current_placeholder_refinement() -> None:
    update_description = _frontmatter(_read_text(UPDATE_SKILL))["description"]
    assert isinstance(update_description, str)
    assert "replace placeholder problem, next action, or acceptance criteria" in update_description

    update_text = _normalize_whitespace(_read_text(UPDATE_SKILL))
    assert "Only the focused refinement fields `problem`, `next_action`, and" in update_text
    assert "`acceptance_criteria` may change ticket body sections" in update_text
    assert "Reject requests to replace unrelated sections" in update_text
    assert "ticket_update.py prepare" in update_text

    readme = _read_text(PLUGIN_ROOT / "README.md")
    assert "placeholder-field updates through preview-first workflow commands" not in readme
    assert "Update existing ticket metadata, lifecycle, or placeholders" not in readme
    assert "Preview-first existing-ticket refinement via `ticket_workflow.py`" not in readme

    handbook = _read_text(PLUGIN_ROOT / "HANDBOOK.md")
    normalized_handbook = _normalize_whitespace(handbook).lower()
    assert "lifecycle, metadata, and placeholder refinement" not in normalized_handbook
    assert "future dedicated `ticket_update.py` backend" not in normalized_handbook
    assert "no dedicated `ticket_update.py` backend exists yet" not in normalized_handbook
    assert "ticket_update.py prepare" in normalized_handbook
    assert "ticket_update.py execute" in normalized_handbook
    assert "preferred way to create or mutate tickets" not in normalized_handbook
    assert "`ticket_workflow.py` is a compatibility/debug runner" in normalized_handbook


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

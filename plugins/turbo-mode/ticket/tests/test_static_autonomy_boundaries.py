"""Static boundary checks for runtime-first Ticket autonomy."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from scripts.ticket_turn_batch import validate_pending_summary_event, validate_repo_context

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PLUGIN_ROOT / "scripts"
TESTS_ROOT = PLUGIN_ROOT / "tests"
CURRENT_FACING_DOCS = (
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
)
ADJACENT_CURRENT_DOCS = (
    PLUGIN_ROOT / "PRIVACY.md",
    PLUGIN_ROOT / "TERMS.md",
    PLUGIN_ROOT / "CHANGELOG.md",
)
AUTONOMY_CLI = SCRIPTS_ROOT / "ticket_autonomy.py"
TURN_BATCH = SCRIPTS_ROOT / "ticket_turn_batch.py"
ENGINE_AGENT = SCRIPTS_ROOT / "ticket_engine_agent.py"
ENGINE_RUNNER = SCRIPTS_ROOT / "ticket_engine_runner.py"
ENGINE_CORE = SCRIPTS_ROOT / "ticket_engine_core.py"

ALLOWED_AUTONOMY_COMMANDS = {
    "pause",
    "recover",
    "apply-turn",
    "doctor-ledger",
    "migrate-change-history",
}
RAW_LEDGER_COMMANDS = {
    "append-event",
    "consume-approval",
    "mark-summarized",
    "rewrite-ledger",
    "delete-event",
}
FORBIDDEN_CURRENT_DOC_STRINGS = (
    "autonomy_mode: auto_audit",
    "autonomy_mode: auto_silent",
    "autonomy_mode: suggest",
    "defaults to `suggest`",
    "created automatically on the first agent mutation",
    "creates `.audit`",
)
FORBIDDEN_STALE_GATEWAY_STRINGS = (
    "runtime-first gateway once implemented",
    "until the runtime-first gateway",
    "runtime-first gateway lands",
    "runtime-first gateway not yet available",
    "wait for the gateway implementation",
)
OLD_MODE_FIXTURE_STRINGS = (
    "auto_audit",
    "auto_silent",
    "autonomy_mode: auto_audit",
    "autonomy_mode: auto_silent",
    "autonomy_mode: suggest",
    '"mode":"suggest"',
    '"mode": "suggest"',
    "defaults to `suggest`",
)
ALLOWED_OLD_MODE_TEST_FUNCTIONS = {
    "test_agent_execute_old_autonomy_modes_require_gateway_decision",
    "test_historical_audit_reader_still_counts_existing_files",
    "test_invalid_config_requires_setup",
    "test_current_docs_describe_audit_as_historical_only",
}
ALLOWED_TICKET_WRITE_SITES = {
    ("ticket_autonomy.py", "_run_migrate_change_history"),
    ("ticket_engine_core.py", "_execute_close"),
    ("ticket_engine_core.py", "_execute_reopen"),
    ("ticket_engine_core.py", "_execute_update"),
    ("ticket_engine_core.py", "_write_text_exclusive"),
}
ALLOWED_AUDIT_WRITE_SITES = {
    ("ticket_audit.py", "repair_audit_logs"),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _module(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _function_ranges(tree: ast.Module) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            if node.decorator_list:
                start = min(start, *(decorator.lineno for decorator in node.decorator_list))
            ranges.append((node.name, start, node.end_lineno or node.lineno))
    return ranges


def _enclosing_function(ranges: list[tuple[str, int, int]], line: int) -> str | None:
    matches = [name for name, start, end in ranges if start <= line <= end]
    return matches[-1] if matches else None


def _string_constants(tree: ast.AST) -> Iterator[ast.Constant]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _write_calls(path: Path) -> Iterator[tuple[str, ast.Call, str]]:
    source = _read(path)
    tree = ast.parse(source, filename=str(path))
    ranges = _function_ranges(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in {"write_text", "write", "open"}:
            continue
        segment = ast.get_source_segment(source, node) or ""
        yield _enclosing_function(ranges, node.lineno) or "<module>", node, segment


def _valid_repo_context(**overrides: object) -> dict[str, object]:
    context: dict[str, object] = {
        "repo_root": "/repo",
        "worktree_root": "/repo",
        "repo_fingerprint": "repo-fp",
        "branch": "feature/runtime",
        "head": "abc123",
    }
    context.update(overrides)
    return context


def _valid_attempt_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schema": "codex.ticket.pending_summary.v1",
        "event_id": "evt_123",
        "timestamp": "2026-05-27T12:00:00Z",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "event_type": "mutation_attempt",
        "status": "pending",
        "action": "update",
        "ticket_id": "T-20260527-01",
        "mutation_id": "mut_123",
        "repo_context": _valid_repo_context(),
        "reason": "test",
        "details": {
            "decision": "apply_autonomously",
            "current_mode": "agent_primary",
            "approval": {"approval_id": "appr_123", "decision": "apply_autonomously"},
            "evidence_kind": "runtime_context",
        },
    }
    event.update(overrides)
    return event


def test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        normalized = _normalize(text)
        assert "`discussion_only`" in normalized
        assert "`preview`" in normalized
        assert "`agent_primary`" in normalized
        assert "strict JSON" in normalized
        for forbidden in FORBIDDEN_CURRENT_DOC_STRINGS:
            assert forbidden not in text, f"{path} contains legacy autonomy guidance"


def test_current_facing_docs_separate_source_boundary_from_installed_runtime_proof() -> None:
    forbidden_success_claims = (
        "installed behavior is confirmed",
        "installed runtime behavior is confirmed",
        "installed runtime proof passed",
        "installed runtime is refreshed",
    )
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        normalized = _normalize(text)
        assert "not installed-runtime proof" in normalized
        for claim in forbidden_success_claims:
            assert claim not in normalized.lower()


def test_current_facing_docs_route_future_history_to_ticket_history_and_pending_summary() -> None:
    for path in CURRENT_FACING_DOCS:
        normalized = _normalize(_read(path))
        assert "Future autonomous durable history writes to `## Change History`" in normalized
        assert "`.codex/ticket-workspace/ticket.pending-summary.jsonl`" in normalized
        assert "Existing `docs/tickets/.audit/` files are historical artifacts" in normalized
        assert "read/repair tools for existing historical `.audit/` files only" in normalized


def test_runtime_first_closeout_docs_do_not_describe_gateway_as_future_work() -> None:
    paths = (*CURRENT_FACING_DOCS, *ADJACENT_CURRENT_DOCS, ENGINE_AGENT, ENGINE_RUNNER)
    for path in paths:
        text = _read(path)
        for forbidden in FORBIDDEN_STALE_GATEWAY_STRINGS:
            assert forbidden not in text, f"{path} contains stale gateway wording: {forbidden}"


def test_adjacent_current_docs_describe_runtime_first_artifacts() -> None:
    privacy = _read(PLUGIN_ROOT / "PRIVACY.md")
    normalized_privacy = _normalize(privacy)
    terms = _read(PLUGIN_ROOT / "TERMS.md")
    normalized_terms = _normalize(terms)
    changelog = _read(PLUGIN_ROOT / "CHANGELOG.md").split("## 1.4.0", maxsplit=1)[0]
    normalized_changelog = _normalize(changelog)

    assert "`.codex/ticket-workspace/ticket.pending-summary.jsonl`" in privacy
    assert "Existing `docs/tickets/.audit/` files are historical artifacts" in normalized_privacy
    assert "pending-summary state, processed envelopes, or historical audit logs" in privacy
    assert (
        "local Ticket workspace state, processed envelopes, and historical audit logs"
        in normalized_terms
    )
    assert "Runtime-first Ticket autonomy source support" in changelog
    assert "not installed-runtime proof" in normalized_changelog
    assert "no longer writes active `docs/tickets/.audit/`" in changelog
    assert "legacy `suggest`, `auto_audit`, or `auto_silent` modes" in changelog


def test_ticket_autonomy_cli_exposes_ticket_level_commands_not_raw_ledger_mutators() -> None:
    tree = _module(AUTONOMY_CLI)
    commands: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_parser":
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                commands.add(value)

    assert commands == ALLOWED_AUTONOMY_COMMANDS
    assert commands.isdisjoint(RAW_LEDGER_COMMANDS)


def test_pending_summary_validation_requires_live_repo_identity_fields() -> None:
    missing_repo_context = _valid_attempt_event()
    missing_repo_context.pop("repo_context")
    assert validate_pending_summary_event(missing_repo_context).ok is False

    detached_head = _valid_repo_context(branch=None)
    assert validate_repo_context(detached_head).ok is True
    missing_head = _valid_repo_context(head=None)
    assert validate_repo_context(missing_head).ok is False
    no_git_metadata = _valid_repo_context(branch=None, head=None)
    assert validate_repo_context(no_git_metadata).ok is True
    mismatched_worktree = _valid_repo_context(worktree_root="/other")
    assert validate_repo_context(mismatched_worktree).ok is False


def test_apply_turn_verifies_repo_context_before_discovery_and_reuses_live_context() -> None:
    source = _read(AUTONOMY_CLI)
    tree = ast.parse(source, filename=str(AUTONOMY_CLI))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    run_apply_turn = functions["_run_apply_turn"]
    assert run_apply_turn.index("verify_turn_repo_context") < run_apply_turn.index(
        "_run_apply_turn_with_mode(project_root, context, repo_context"
    )
    assert "discover_candidate_mutations" not in run_apply_turn

    with_mode = functions["_run_apply_turn_with_mode"]
    assert "repo_context: VerifiedRepoContext" in with_mode
    assert with_mode.index("discover_candidate_mutations") < with_mode.index(
        "apply_autonomous_mutation("
    )
    assert "repo_context=repo_context" in with_mode
    assert "_append_non_write_decision(" in with_mode
    assert "_append_summary_receipt(" in with_mode


def test_active_ticket_write_sites_are_named_functions_not_helper_file_allowlists() -> None:
    violations: list[str] = []
    for path in SCRIPTS_ROOT.glob("*.py"):
        for function, node, segment in _write_calls(path):
            if "ticket_path" not in segment:
                continue
            site = (path.name, function)
            if site not in ALLOWED_TICKET_WRITE_SITES:
                violations.append(f"{path.name}:{node.lineno}:{function}:{segment}")

    assert violations == []


def test_direct_agent_and_runner_cannot_bypass_gateway_decision_contract() -> None:
    agent = _read(ENGINE_AGENT)
    runner = _read(ENGINE_RUNNER)
    core = _read(ENGINE_CORE)

    assert "Direct execute is not an autonomous write route" in _normalize(agent)
    assert "apply_autonomous_mutation" not in agent
    assert "apply_autonomous_mutation" not in runner
    assert (
        'runtime_execute_surface = "direct_execute" if request_origin == "agent" else None'
        in runner
    )
    assert "runtime_execute_surface=runtime_execute_surface" in runner
    assert 'runtime_execute_surface == "direct_execute"' in core
    assert "Direct agent execute requires a gateway-approved decision" in core
    assert 'error_code="gateway_required"' in core


def test_future_source_does_not_write_audit_logs_except_historical_repair() -> None:
    violations: list[str] = []
    for path in SCRIPTS_ROOT.glob("*.py"):
        source = _read(path)
        tree = ast.parse(source, filename=str(path))
        ranges = _function_ranges(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node) not in {"write_text", "write", "open"}:
                continue
            function = _enclosing_function(ranges, node.lineno) or "<module>"
            function_source = ""
            for func_node in ast.walk(tree):
                if isinstance(func_node, ast.FunctionDef) and func_node.name == function:
                    function_source = ast.get_source_segment(source, func_node) or ""
                    break
            if ".audit" not in function_source:
                continue
            site = (path.name, function)
            if site not in ALLOWED_AUDIT_WRITE_SITES:
                segment = ast.get_source_segment(source, node) or ""
                violations.append(f"{path.name}:{node.lineno}:{function}:{segment}")

    assert violations == []


def test_legacy_test_strings_are_only_negative_or_historical_fixtures() -> None:
    violations: list[str] = []
    for path in TESTS_ROOT.glob("test_*.py"):
        if path.name == "test_static_autonomy_boundaries.py":
            continue
        source = _read(path)
        tree = ast.parse(source, filename=str(path))
        ranges = _function_ranges(tree)
        for node in _string_constants(tree):
            value = node.value
            if not any(old in value for old in OLD_MODE_FIXTURE_STRINGS):
                continue
            function = _enclosing_function(ranges, node.lineno)
            if function not in ALLOWED_OLD_MODE_TEST_FUNCTIONS:
                violations.append(f"{path.name}:{node.lineno}:{function}:{value}")

    assert violations == []


def test_runtime_readiness_source_does_not_stage_legacy_yaml_autonomy_config() -> None:
    text = _read(SCRIPTS_ROOT / "ticket_runtime_readiness.py")
    assert "autonomy_mode: auto_audit" not in text
    assert "autonomy_mode: auto_silent" not in text
    assert "autonomy_mode: suggest" not in text
    assert '"mode":"suggest"' not in text
    assert '"mode": "suggest"' not in text

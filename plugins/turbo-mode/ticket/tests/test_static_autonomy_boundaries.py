"""Static boundary checks for runtime-first Ticket autonomy."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

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
ENGINE_AGENT = SCRIPTS_ROOT / "ticket_engine_agent.py"
ENGINE_RUNNER = SCRIPTS_ROOT / "ticket_engine_runner.py"
TARGET_RUNTIME_MODES = ("agent_primary", "discussion_only")

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


def test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        target = _target_sections(text)
        target_normalized = _normalize(target)
        for mode in TARGET_RUNTIME_MODES:
            assert f"`{mode}`" in target
        assert "`preview`" not in target
        assert "persistent `preview`" not in target_normalized
        if "`preview`" in text:
            allowed = _deprecated_or_diagnostic_sections(text)
            assert "`preview`" in allowed
            assert "diagnostic" in _normalize(allowed).lower() or "deprecated" in _normalize(
                allowed
            ).lower()
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
        text = _read(path)
        history = _section(text, "## Target Change History Grammar", "\n## ")
        normalized_history = _normalize(history)
        assert "- <timestamp> | <actor> | <reason>" in history
        assert "Corrects: <reference>" in history
        assert "actor" in normalized_history
        assert "not a workflow label" in normalized_history
        assert "auto-create" not in history
        assert "auto-update" not in history
        target = _target_sections(text)
        assert "approval state" not in _normalize(target).lower()
        pending_summary_path = "`.codex/ticket-workspace/ticket.pending-summary.jsonl`"
        if pending_summary_path in text:
            assert pending_summary_path in _deprecated_or_diagnostic_sections(text)


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
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        target = _target_sections(text)
        assert "ticket_autonomy.py apply-turn" not in target
        assert "raw ledger" not in _normalize(target).lower()
        if "ticket_autonomy.py apply-turn" in text:
            assert "ticket_autonomy.py apply-turn" in _deprecated_or_diagnostic_sections(text)


def test_pending_summary_validation_requires_live_repo_identity_fields() -> None:
    for path in CURRENT_FACING_DOCS:
        target = _target_sections(_read(path))
        normalized = _normalize(target).lower()
        assert "approval" not in normalized
        assert "pending-summary" not in normalized


def test_apply_turn_verifies_repo_context_before_discovery_and_reuses_live_context() -> None:
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        target = _target_sections(text)
        assert "apply-turn" not in target
        assert "discover_candidate_mutations" not in target
        assert "apply_autonomous_mutation" not in target
        assert "target candidate mutation" in _normalize(target).lower()


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
    for path in CURRENT_FACING_DOCS:
        text = _read(path)
        target = _target_sections(text)
        assert "direct_execute" not in target
        assert "gateway-approved decision" not in target
        assert "`gateway_required`" not in target
        if "direct_execute" in text:
            assert "direct_execute" in _deprecated_or_diagnostic_sections(text)


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

from __future__ import annotations

from pathlib import Path

from migration_common import (
    EVIDENCE_ROOT,
    REPO_ROOT,
    base_run_metadata,
    copy_exact_files,
    fail,
    file_manifest,
    main_with_errors,
    parse_common_args,
    read_sha256sums,
    write_json,
    write_sha256sums,
)

TOOL_PATH = "plugins/turbo-mode/tools/migration/copy_ticket_source.py"
DEFAULT_SOURCE = Path("/Users/jp/.codex/plugins/plugin-dev/turbo-mode/ticket/1.4.0")
DEFAULT_OUTPUT = REPO_ROOT / "plugins/turbo-mode/ticket/1.4.0"
DEFAULT_PRECOPY = EVIDENCE_ROOT / "ticket-source-precopy.SHA256SUMS"
DEFAULT_POSTCOPY = EVIDENCE_ROOT / "ticket-source-postcopy.SHA256SUMS"

ALLOWLIST = {
    ".codex-plugin/plugin.json",
    "CHANGELOG.md",
    "HANDBOOK.md",
    "README.md",
    "agents/.gitkeep",
    "hooks/hooks.json",
    "hooks/ticket_engine_guard.py",
    "pyproject.toml",
    "references/.gitkeep",
    "references/ticket-contract.md",
    "scripts/.gitkeep",
    "scripts/__init__.py",
    "scripts/ticket_audit.py",
    "scripts/ticket_dedup.py",
    "scripts/ticket_engine_agent.py",
    "scripts/ticket_engine_core.py",
    "scripts/ticket_engine_runner.py",
    "scripts/ticket_engine_user.py",
    "scripts/ticket_envelope.py",
    "scripts/ticket_id.py",
    "scripts/ticket_parse.py",
    "scripts/ticket_paths.py",
    "scripts/ticket_read.py",
    "scripts/ticket_render.py",
    "scripts/ticket_stage_models.py",
    "scripts/ticket_triage.py",
    "scripts/ticket_trust.py",
    "scripts/ticket_ux.py",
    "scripts/ticket_validate.py",
    "scripts/ticket_workflow.py",
    "skills/ticket-triage/SKILL.md",
    "skills/ticket/SKILL.md",
    "skills/ticket/references/pipeline-guide.md",
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/support/__init__.py",
    "tests/support/builders.py",
    "tests/support/workflow.py",
    "tests/test_audit.py",
    "tests/test_autonomy.py",
    "tests/test_autonomy_integration.py",
    "tests/test_blocker_resolution.py",
    "tests/test_classify.py",
    "tests/test_dedup.py",
    "tests/test_dedup_persistence.py",
    "tests/test_docs_contract.py",
    "tests/test_doctor.py",
    "tests/test_engine_policy.py",
    "tests/test_entrypoints.py",
    "tests/test_envelope.py",
    "tests/test_execute.py",
    "tests/test_hook.py",
    "tests/test_hook_integration.py",
    "tests/test_id.py",
    "tests/test_ingest.py",
    "tests/test_integration.py",
    "tests/test_migration.py",
    "tests/test_parse.py",
    "tests/test_paths.py",
    "tests/test_plan.py",
    "tests/test_preflight.py",
    "tests/test_read.py",
    "tests/test_release_provenance.py",
    "tests/test_render.py",
    "tests/test_response_models.py",
    "tests/test_review_findings.py",
    "tests/test_runner.py",
    "tests/test_stage_models.py",
    "tests/test_triage.py",
    "tests/test_trust.py",
    "tests/test_ux.py",
    "tests/test_validate.py",
    "tests/test_workflow.py",
    "tests/test_workflow_cli.py",
    "tests/test_workflow_execute.py",
    "tests/test_workflow_recovery.py",
    "uv.lock",
}

EXCLUDED_PREFIXES = (
    ".codex/ticket-tmp/",
    "docs/tickets/",
    "docs/superpowers/plans/",
)
EXCLUDED_NAMES = {".DS_Store", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}


def classify_source(source_root: Path) -> tuple[dict[str, str], list[str], list[str]]:
    all_files = file_manifest(source_root)
    allowlisted: dict[str, str] = {}
    excluded: list[str] = []
    unknown: list[str] = []
    for rel, digest in sorted(all_files.items()):
        if rel in ALLOWLIST:
            allowlisted[rel] = digest
            continue
        has_excluded_part = any(part in EXCLUDED_NAMES for part in Path(rel).parts)
        if rel.startswith(EXCLUDED_PREFIXES) or has_excluded_part:
            excluded.append(rel)
            continue
        unknown.append(rel)
    missing = sorted(ALLOWLIST - set(allowlisted))
    if missing:
        fail("classify ticket source", "allowlisted files missing", missing)
    if len(allowlisted) != 77:
        fail("classify ticket source", "allowlisted file count mismatch", len(allowlisted))
    if unknown:
        fail("classify ticket source", "unknown non-allowlisted files", unknown)
    return allowlisted, excluded, unknown


def run_copy(args: object) -> None:
    source_root = args.source_root
    manifest_path = args.manifest
    output_root = args.output_root
    metadata = base_run_metadata(run_id=args.run_id, mode="copy-ticket-source", tool_path=TOOL_PATH)

    if args.generate_manifest:
        manifest, excluded, unknown = classify_source(source_root)
        write_sha256sums(manifest_path, manifest, metadata=metadata)
        write_json(
            EVIDENCE_ROOT / "ticket-source-allowlist.summary.json",
            {
                "run_metadata": metadata,
                "allowlisted_file_count": len(manifest),
                "excluded_non_package_file_count": len(excluded),
                "unknown_file_count": len(unknown),
            },
        )
    else:
        manifest = read_sha256sums(manifest_path)

    copied = copy_exact_files(source_root, output_root, manifest)
    write_sha256sums(args.postcopy, copied, metadata=metadata)
    print(f"ticket source copied: {len(copied)} files")


def main() -> None:
    parser = parse_common_args("Copy Ticket source with an explicit allowlist.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_PRECOPY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--postcopy", type=Path, default=DEFAULT_POSTCOPY)
    parser.add_argument("--generate-manifest", action="store_true")
    args = parser.parse_args()
    run_copy(args)


if __name__ == "__main__":
    main_with_errors(main)

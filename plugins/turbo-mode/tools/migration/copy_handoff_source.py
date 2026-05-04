from __future__ import annotations

import shutil
from pathlib import Path

from migration_common import (
    EVIDENCE_ROOT,
    REPO_ROOT,
    base_run_metadata,
    copy_exact_files,
    extract_safe,
    fail,
    main_with_errors,
    parse_common_args,
    read_sha256sums,
    sha256_file,
    write_json,
    write_sha256sums,
)

TOOL_PATH = "plugins/turbo-mode/tools/migration/copy_handoff_source.py"
DEFAULT_ARCHIVE = Path(
    "/Users/jp/.codex/dist/turbo-mode-handoff-1.6.0-non-hook-closeout/"
    "turbo-mode-handoff-1.6.0-non-hook-with-ticket-1.4.0.tgz"
)
DEFAULT_MANIFEST = Path(
    "/Users/jp/.codex/dist/turbo-mode-handoff-1.6.0-non-hook-closeout/source-files.SHA256SUMS"
)
DEFAULT_OUTPUT = REPO_ROOT / "plugins/turbo-mode/handoff/1.6.0"
DEFAULT_POSTCOPY = EVIDENCE_ROOT / "handoff-source-postcopy.SHA256SUMS"


def handoff_subset(manifest_path: Path) -> dict[str, str]:
    source_manifest = read_sha256sums(manifest_path)
    subset: dict[str, str] = {}
    for rel, digest in source_manifest.items():
        prefix = "handoff/1.6.0/"
        if rel.startswith(prefix):
            subset[rel.removeprefix(prefix)] = digest
    if len(subset) != 45:
        fail("select handoff manifest", "expected 45 files", len(subset))
    return subset


def run_copy(args: object) -> None:
    metadata = base_run_metadata(
        run_id=args.run_id,
        mode="copy-handoff-source",
        tool_path=TOOL_PATH,
    )
    if args.scratch_root.exists():
        shutil.rmtree(args.scratch_root)
    extract_safe(args.archive, args.scratch_root)
    subset = handoff_subset(args.manifest)
    extracted_root = args.scratch_root / "handoff/1.6.0"
    copied = copy_exact_files(extracted_root, args.output_root, subset)
    write_sha256sums(args.postcopy, copied, metadata=metadata)
    write_json(
        EVIDENCE_ROOT / "handoff-copy.summary.json",
        {
            "run_metadata": metadata,
            "archive": str(args.archive),
            "archive_sha256": sha256_file(args.archive),
            "manifest": str(args.manifest),
            "manifest_sha256": sha256_file(args.manifest),
            "copied_file_count": len(copied),
        },
    )
    print(f"handoff source copied: {len(copied)} files")


def main() -> None:
    parser = parse_common_args("Copy Handoff source from the certified dist archive.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--postcopy", type=Path, default=DEFAULT_POSTCOPY)
    args = parser.parse_args()
    run_copy(args)


if __name__ == "__main__":
    main_with_errors(main)

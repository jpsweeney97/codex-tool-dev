"""Black-box characterization of the deliberate validator CLI.

This net pins the public process boundary that the validator refactor must preserve.
It never imports validator helpers. Inputs are chosen by branch: every help surface,
all four exit classes, append-only store writes, envelope acceptance/refusal, capsule
validation/import/refusal, and the embedded fixture control. Temporary paths are the
only variable output; assertions either derive their canonical value at runtime or
avoid snapshotting them. Locale and hash ordering are fixed for every subprocess.

These tests pin observed behavior, not correctness. They detect changes only in the
public behaviors exercised here and do not claim full or equivalent coverage.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from functools import cache
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "deliberate-validate.py"
CONTRACT_DATA = ROOT / "references" / "contract-data.yaml"
VALID_CAPSULE = Path(__file__).parent / "fixtures" / "valid-capsule.yaml"
EXPECTED_GENERATE_BRIEF_ID = (
    "b1cacc16754f1051eb412f9182e5eec688fd8bc550ee65ff3e821eab9cfb0818"
)

COMMAND_HELP = {
    "identity": "usage: deliberate-validate.py identity [-h] --data DATA [--as-evidence | --as-in-packet] paths [paths ...]",
    "init-setup": "usage: deliberate-validate.py init-setup [-h] --data DATA --store STORE --run RUN --setup SETUP",
    "write-item": "usage: deliberate-validate.py write-item [-h] --data DATA --store STORE --kind KIND [--stage STAGE] body",
    "record-proof-inputs": "usage: deliberate-validate.py record-proof-inputs [-h] --data DATA --store STORE [--body PATH] [BODY]",
    "record-terminal": "usage: deliberate-validate.py record-terminal [-h] --data DATA --store STORE --terminal TERMINAL --carrier CARRIER",
    "validate-runstate-item": "usage: deliberate-validate.py validate-runstate-item [-h] --data DATA item",
    "render-brief": "usage: deliberate-validate.py render-brief [-h] --data DATA --store STORE --stage STAGE [--items ITEMS]",
    "validate-envelope": "usage: deliberate-validate.py validate-envelope [-h] --data DATA --store STORE [--stage STAGE] [--accept] envelope",
    "validate-capsule": "usage: deliberate-validate.py validate-capsule [-h] --data DATA [--store STORE] [--accept] [--file-capsule] capsule",
    "import-capsule": "usage: deliberate-validate.py import-capsule [-h] --data DATA --store STORE --run RUN --capsule CAPSULE [--file-capsule] [--revive REVIVE] [--constraint-withdrawn CONSTRAINT_WITHDRAWN] [--accept-seed] [--echo-body ECHO_BODY] --pins-body PINS_BODY [--invalidate-from STAGE] [--field-base FIELD_BASE] [--closed-field CLOSED_FIELD] [--directive-manifest DIRECTIVE_MANIFEST]",
    "check-renderings": "usage: deliberate-validate.py check-renderings [-h] --data DATA [--write]",
    "fixtures": "usage: deliberate-validate.py fixtures [-h] --data DATA",
}

COMMAND_DESCRIPTIONS = {
    "identity": "content identifiers for paths (SHA-256, path-kind rules)",
    "init-setup": "normalize one setup document and write echo then decomposition",
    "write-item": "validate and append one run-state item",
    "record-proof-inputs": "record the exact proof-boundary inputs before capsule acceptance",
    "record-terminal": "record the terminal and capsule carrier after assembly fixes the terminal",
    "validate-runstate-item": "validate one run-state item file",
    "render-brief": "render a stage brief from the store per the matrix column",
    "validate-envelope": "validate a returned stage envelope against the store",
    "validate-capsule": "validate a capsule document (fences tolerated)",
    "import-capsule": "validate a pasted capsule and create the re-run store with typed restart state",
    "check-renderings": "compare authored renderings in references/ against the canonical data file",
    "fixtures": "run the must-block/must-pass fixture set",
}


def run_validator(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the public PEP 723 entrypoint in a deterministic subprocess."""
    env = os.environ.copy()
    env.update(
        {
            "LANG": "C",
            "LC_ALL": "C",
            "NO_COLOR": "1",
            "PYTHONHASHSEED": "0",
            "UV_NO_PROGRESS": "1",
        }
    )
    return subprocess.run(
        ["uv", "run", "--script", str(VALIDATOR), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@cache
def contract_data() -> dict[str, object]:
    """Load the live canonical data used to author valid boundary inputs."""
    loaded = yaml.safe_load(CONTRACT_DATA.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def write_yaml(path: Path, value: object) -> Path:
    """Write one deterministic YAML carrier for a subprocess input."""
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def compact_usage(help_text: str) -> str:
    """Collapse argparse line wrapping in the usage paragraph only."""
    return " ".join(help_text.split("\n\n", 1)[0].split())


def compact_text(text: str) -> str:
    """Collapse argparse wrapping without changing token order."""
    return " ".join(text.split())


def setup_document() -> dict[str, object]:
    """Return the smallest setup that reaches store and Generate paths."""
    data = contract_data()
    return {
        "schema": "deliberate-setup/v1",
        "invocation-wording-initial": "characterization invocation",
        "directives": [],
        "directives-collapsed": [],
        "fields": {
            "frame": {
                "value": "choose a note-sync approach for a two-person team",
                "provenance": "user-supplied",
            },
            "field-mode": {"value": "seed-and-widen", "provenance": "default"},
            "constraints": {
                "value": [{"constraint": "must run offline", "price": "no cloud sync"}],
                "provenance": "user-supplied",
            },
            "values": {"value": [], "provenance": "absent"},
            "stakes": {"value": "absent", "provenance": "absent"},
            "evidence-inputs": {
                "value": "none supplied",
                "provenance": "absent",
            },
            "evidence-authorization": {
                "value": "default inspection only",
                "provenance": "default",
            },
            "survivor-budget": {"value": 4, "provenance": "default"},
            "degradation-permission": {
                "value": "absent",
                "provenance": "absent",
            },
        },
        "candidates": [
            {
                "wording": "Option A — file sync over Syncthing",
                "provenance-flag": "user-seed",
            }
        ],
        "soft-preferences": {
            "provenance": "inferred",
            "entries": [
                {
                    "candidate": "Option A — file sync over Syncthing",
                    "criteria": ["ongoing operating burden matters"],
                    "authority-note": {
                        "text": "user lean: called it 'the obvious one'",
                        "provenance": "inferred",
                        "span": "characterization span",
                    },
                }
            ],
        },
        "composition-provenance": {
            "invocation-span": "candidate wording elided here",
            "delegation-span": "candidate selection delegated to the run",
        },
        "bounds": data["bounds"],
        "source-capsule-id": "none",
    }


def pins_body() -> dict[str, object]:
    """Return exact-set current pins using stable synthetic identifiers."""
    validation = contract_data()["validation"]
    assert isinstance(validation, dict)
    constituent_names = validation["constituent-names"]
    method_surfaces = validation["method-surfaces"]
    assert isinstance(constituent_names, list)
    assert isinstance(method_surfaces, list)
    zero_id = "0" * 64
    return {
        "constituents": {
            name: [{"path": f"skills/{name}/SKILL.md", "id": zero_id}]
            for name in constituent_names
        },
        "method": [{"path": surface, "id": zero_id} for surface in method_surfaces],
        "evidence": [],
        "in-packet": [],
    }


def generate_envelope() -> dict[str, object]:
    """Return one observed-valid Generate envelope."""
    return {
        "schema": "deliberate-envelope/v1",
        "stage": "generate",
        "status": "completed",
        "artifacts": {
            "field": [
                {
                    "wording": "Option A — file sync over Syncthing",
                    "provenance": "user-seed",
                },
                {"wording": "Option B — hosted wiki", "provenance": "generated"},
            ],
            "fixed-points-line": (
                "Untouched fixed points: the two-person team size and the must-run-offline constraint."
            ),
        },
        "retrievals": "none",
        "encounters": "none",
        "pins": "none",
        "model": "unknown",
    }


def initialize_store(tmp_path: Path) -> tuple[Path, Path]:
    """Initialize echo/decomposition/pins through public CLI commands."""
    store = tmp_path / "deliberate-run-live"
    setup_path = write_yaml(tmp_path / "setup.yaml", setup_document())
    pins_path = write_yaml(tmp_path / "pins.yaml", pins_body())

    initialized = run_validator(
        "init-setup",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(store),
        "--run",
        "characterization-run",
        "--setup",
        str(setup_path),
    )
    assert initialized.returncode == 0, initialized.stderr
    assert initialized.stdout == (
        f"setup initialized: {store} (echo seq 0, decomposition seq 1, "
        "run characterization-run)\n"
    )
    assert initialized.stderr == ""

    pinned = run_validator(
        "write-item",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(store),
        "--kind",
        "pins",
        str(pins_path),
    )
    assert pinned.returncode == 0, pinned.stderr
    assert pinned.stdout == "item written: 002-pins.yaml\n"
    assert pinned.stderr == ""
    return store, pins_path


def store_manifest(store: Path) -> list[tuple[str, int, str, str | None]]:
    """Read only the append identity fields from persisted YAML items."""
    manifest = []
    for path in sorted(store.glob("*.yaml")):
        item = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest.append((path.name, item["seq"], item["kind"], item.get("stage")))
    return manifest


def test_cli_help_surface_is_stable() -> None:
    """Pin command order, descriptions, and every subcommand usage signature."""
    root_help = run_validator("--help")
    assert root_help.returncode == 0
    assert root_help.stderr == ""
    compact_root = compact_text(root_help.stdout)
    assert "exit codes: 0 pass, 1 fail, 2 refusal, 4 store read loss" in compact_root
    assert list(COMMAND_HELP) == list(COMMAND_DESCRIPTIONS)
    for command, description in COMMAND_DESCRIPTIONS.items():
        assert command in compact_root
        assert description in compact_root

    for command, expected_usage in COMMAND_HELP.items():
        result = run_validator(command, "--help")
        assert result.returncode == 0, command
        assert result.stderr == "", command
        assert compact_usage(result.stdout) == expected_usage


def test_exit_codes_and_contractual_messages_are_stable(tmp_path: Path) -> None:
    """Exercise pass, validation failure, refusal, and store-read-loss exits."""
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("characterization\n", encoding="utf-8")
    passed = run_validator("identity", "--data", str(CONTRACT_DATA), str(evidence))
    assert passed.returncode == 0
    assert passed.stderr == ""
    assert yaml.safe_load(passed.stdout) == {
        "identities": [
            {
                "path": str(evidence),
                "id": hashlib.sha256(b"characterization\n").hexdigest(),
            }
        ],
        "total-bytes": 17,
    }

    invalid_item = write_yaml(tmp_path / "invalid-item.yaml", {})
    failed = run_validator(
        "validate-runstate-item",
        "--data",
        str(CONTRACT_DATA),
        str(invalid_item),
    )
    assert failed.returncode == 1
    assert failed.stdout == ""
    assert (
        failed.stderr
        == "run-state item validation failed: missing required key: schema.\n"
    )

    refused = run_validator(
        "identity",
        "--data",
        str(CONTRACT_DATA),
        "--as-in-packet",
        str(tmp_path),
    )
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert refused.stderr == (
        "identity refused: --as-in-packet accepts only exact serialized payload files, "
        "never directories.\n"
    )

    empty_store = tmp_path / "empty-store"
    empty_store.mkdir()
    lost = run_validator(
        "render-brief",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(empty_store),
        "--stage",
        "generate",
    )
    assert lost.returncode == 4
    assert lost.stdout == ""
    assert lost.stderr == ("store read failed: required run-state item absent: echo\n")


def test_store_sequence_and_envelope_accept_reject_round_trip(
    tmp_path: Path,
) -> None:
    """Pin setup writes, brief recording, and envelope acceptance atomicity."""
    store, _ = initialize_store(tmp_path)
    assert store_manifest(store) == [
        ("000-echo.yaml", 0, "echo", None),
        ("001-decomposition.yaml", 1, "decomposition", None),
        ("002-pins.yaml", 2, "pins", None),
    ]

    rendered = run_validator(
        "render-brief",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(store),
        "--stage",
        "generate",
    )
    assert rendered.returncode == 0, rendered.stderr
    assert rendered.stdout.startswith(
        "You are the generate stage of one `deliberate` run."
    )
    brief_id = hashlib.sha256(rendered.stdout.encode("utf-8")).hexdigest()
    assert brief_id == EXPECTED_GENERATE_BRIEF_ID
    assert rendered.stderr == (
        f"brief-id: {EXPECTED_GENERATE_BRIEF_ID} "
        "(recorded in run state before dispatch)\n"
    )

    envelope_path = write_yaml(tmp_path / "generate-envelope.yaml", generate_envelope())
    accepted = run_validator(
        "validate-envelope",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(store),
        "--stage",
        "generate",
        "--accept",
        str(envelope_path),
    )
    assert accepted.returncode == 0, accepted.stderr
    assert accepted.stdout == (
        "envelope valid: stage=generate status='completed' recorded with 0 "
        "concerns amendment(s)\n"
    )
    assert accepted.stderr == ""
    expected_manifest = [
        ("000-echo.yaml", 0, "echo", None),
        ("001-decomposition.yaml", 1, "decomposition", None),
        ("002-pins.yaml", 2, "pins", None),
        ("003-brief-render-generate.yaml", 3, "brief-render", "generate"),
        ("004-envelope-generate.yaml", 4, "envelope", "generate"),
    ]
    assert store_manifest(store) == expected_manifest

    rejected = run_validator(
        "validate-envelope",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(store),
        "--stage",
        "prune",
        "--accept",
        str(envelope_path),
    )
    assert rejected.returncode == 1
    assert rejected.stdout == ""
    assert rejected.stderr == (
        "envelope validation failed: envelope stage 'generate' does not match the "
        "dispatched stage 'prune'.\n"
    )
    assert store_manifest(store) == expected_manifest


def test_capsule_validate_import_and_reject_round_trip(tmp_path: Path) -> None:
    """Pin standalone capsule validation plus atomic import and refusal paths."""
    validated = run_validator(
        "validate-capsule",
        "--data",
        str(CONTRACT_DATA),
        str(VALID_CAPSULE),
    )
    assert validated.returncode == 0, validated.stderr
    assert validated.stdout == (
        "capsule valid: run=fixture-capsule-run terminal='close rendered'\n"
    )
    assert validated.stderr == ""

    original = VALID_CAPSULE.read_text(encoding="utf-8")
    tampered_text = original.replace(
        "fixture comparison surface", "tampered comparison surface", 1
    )
    tampered = tmp_path / "tampered-capsule.yaml"
    tampered.write_text(tampered_text, encoding="utf-8")
    terminator = original.rsplit("capsule-complete: ", 1)[1].strip()
    prefix = tampered_text.rsplit("capsule-complete: ", 1)[0].encode("utf-8")
    actual = hashlib.sha256(prefix).hexdigest()
    rejected = run_validator(
        "validate-capsule",
        "--data",
        str(CONTRACT_DATA),
        str(tampered),
    )
    assert rejected.returncode == 1
    assert rejected.stdout == ""
    assert rejected.stderr == (
        "capsule validation failed: completeness terminator mismatch — the document "
        f"is truncated or altered: declared {terminator[:12]}…, actual "
        f"{actual[:12]}….\n"
    )

    pins_path = write_yaml(tmp_path / "pins.yaml", pins_body())
    imported_store = tmp_path / "imported-run"
    imported = run_validator(
        "import-capsule",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(imported_store),
        "--run",
        "characterization-import",
        "--capsule",
        str(VALID_CAPSULE),
        "--pins-body",
        str(pins_path),
        "--invalidate-from",
        "contest",
    )
    assert imported.returncode == 0, imported.stderr
    assert imported.stdout == (
        f"capsule imported: store={Path(os.path.realpath(imported_store))} "
        "run=characterization-import (echo, decomposition, pins, capsule-import, "
        "restart-plan written)\n"
    )
    assert imported.stderr == ""
    assert store_manifest(imported_store) == [
        ("000-echo.yaml", 0, "echo", None),
        ("001-decomposition.yaml", 1, "decomposition", None),
        ("002-pins.yaml", 2, "pins", None),
        ("003-capsule-import.yaml", 3, "capsule-import", None),
        ("004-restart-plan.yaml", 4, "restart-plan", None),
    ]

    refused_store = tmp_path / "refused-import"
    refused = run_validator(
        "import-capsule",
        "--data",
        str(CONTRACT_DATA),
        "--store",
        str(refused_store),
        "--run",
        "unclassified-import",
        "--capsule",
        str(VALID_CAPSULE),
        "--pins-body",
        str(pins_path),
    )
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert refused.stderr == (
        "capsule import refused: completed capsule has no classified re-run directive "
        "or invalidation.\n"
    )
    assert not refused_store.exists()


def test_embedded_fixture_summary_is_stable() -> None:
    """Keep the existing executable fixture suite as the control (one method-pin
    drift case is derived per method surface, so the eighth surface grew the
    count from 158 to 159; the v30 field-not-ready close-less envelope cases
    grew it to 162)."""
    result = run_validator("fixtures", "--data", str(CONTRACT_DATA))
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.endswith("\n162/162 fixtures behaved as required\n")
    assert (
        len(re.findall(r"^(?:PASS|FAIL)  ", result.stdout, flags=re.MULTILINE)) == 162
    )

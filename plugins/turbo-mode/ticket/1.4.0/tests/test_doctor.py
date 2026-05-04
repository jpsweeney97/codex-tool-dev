from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.ticket_triage import DoctorInputError, _source_cache_report, _tree_manifest, ticket_doctor


def test_ticket_doctor_reports_project_and_plugin_paths(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
    )

    assert report["project"]["tickets_dir"] == str(tmp_tickets)
    assert report["plugin"]["plugin_root"] == str(plugin_root)
    assert report["plugin"]["cache_root"] == str(plugin_root)
    assert report["plugin"]["source_cache_equal"] is True
    assert report["runtime"]["live_hook_probe"] == "not_run"


def test_source_cache_report_reports_missing_cache(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    missing_cache = tmp_path / "missing-cache"

    report = _source_cache_report(plugin_root, missing_cache)

    assert report["cache_exists"] is False
    assert report["source_cache_equal"] is False


def test_ticket_doctor_detects_same_size_content_divergence(tmp_tickets: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "same.py").write_text("alpha\n", encoding="utf-8")
    (cache / "same.py").write_text("bravo\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["same.py"]


def test_ticket_doctor_source_cache_equal_is_exact_not_filtered(tmp_tickets: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / ".audit").mkdir()
    (source / ".audit" / "source-only.jsonl").write_text("audit\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == [".audit/source-only.jsonl"]


def test_ticket_doctor_source_cache_equal_detects_empty_directory_difference(tmp_tickets: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "empty-source-only").mkdir()

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["empty-source-only"]


def test_ticket_doctor_source_cache_equal_detects_file_kind_difference(tmp_tickets: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / "kind").mkdir()
    (cache / "kind").write_text("kind\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["source_cache_mismatches"] == ["kind"]


def test_ticket_doctor_reports_generated_residue_separately(tmp_tickets: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    source.mkdir()
    cache.mkdir()
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "README.md").write_text("cache\n", encoding="utf-8")

    report = _source_cache_report(source, cache)

    assert report["source_cache_equal"] is False
    assert report["generated_residue"] == [
        "source:.pytest_cache",
        "source:.pytest_cache/README.md",
    ]


def test_ticket_doctor_classifies_live_hook_probe_output(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    probe_output = tmp_path / "hook-probe.out"
    probe_output.write_text(
        "\n".join([
            json.dumps({
                "id": 1,
                "result": {
                    "plugin": {
                        "summary": {
                            "id": "ticket@turbo-mode",
                            "enabled": True,
                            "installed": True,
                        },
                        "marketplacePath": "/Users/jp/.agents/plugins/marketplace.json",
                    },
                },
            }),
            json.dumps({
                "id": 2,
                "result": {
                    "data": [{
                        "warnings": [],
                        "errors": [],
                        "hooks": [{
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": f"python3 {plugin_root}/hooks/ticket_engine_guard.py",
                            "sourcePath": f"{plugin_root}/hooks/hooks.json",
                        }],
                    }],
                },
            }),
        ]),
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
        runtime_probe_output=probe_output,
    )

    assert report["runtime"]["live_hook_probe"] == "proven"
    assert report["runtime"]["ticket_plugin_enabled"] is True
    assert report["runtime"]["ticket_hook_count"] == 1


def test_ticket_doctor_blocks_wrong_hook_event(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    probe_output = tmp_path / "wrong-event.out"
    probe_output.write_text(
        "\n".join([
            json.dumps({
                "id": 1,
                "result": {
                    "plugin": {
                        "summary": {
                            "id": "ticket@turbo-mode",
                            "enabled": True,
                            "installed": True,
                        },
                        "marketplacePath": "/Users/jp/.agents/plugins/marketplace.json",
                    },
                },
            }),
            json.dumps({
                "id": 2,
                "result": {
                    "data": [{
                        "warnings": [],
                        "errors": [],
                        "hooks": [{
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "postToolUse",
                            "matcher": "Bash",
                            "command": f"python3 {plugin_root}/hooks/ticket_engine_guard.py",
                            "sourcePath": f"{plugin_root}/hooks/hooks.json",
                        }],
                    }],
                },
            }),
        ]),
        encoding="utf-8",
    )

    report = ticket_doctor(
        tmp_tickets,
        plugin_root=plugin_root,
        cache_root=plugin_root,
        runtime_probe_output=probe_output,
    )

    assert report["runtime"]["live_hook_probe"] == "blocked"
    assert report["runtime"]["ticket_plugin_enabled"] is True
    assert report["runtime"]["ticket_hook_count"] == 0


@pytest.mark.parametrize("bad_root", [Path("/"), Path("/Users/jp")])
def test_ticket_doctor_rejects_arbitrary_plugin_roots(tmp_tickets: Path, bad_root: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]

    with pytest.raises(DoctorInputError, match="plugin_root"):
        ticket_doctor(tmp_tickets, plugin_root=bad_root, cache_root=plugin_root)


def test_ticket_doctor_rejects_unrelated_cache_root(tmp_tickets: Path, tmp_path: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    unrelated = tmp_path / "unrelated-cache"
    unrelated.mkdir()

    with pytest.raises(DoctorInputError, match="cache_root"):
        ticket_doctor(tmp_tickets, plugin_root=plugin_root, cache_root=unrelated)


def test_cli_doctor_rejects_arbitrary_roots(tmp_tickets: Path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            "python3",
            "-B",
            str(plugin_root / "scripts" / "ticket_triage.py"),
            "doctor",
            str(tmp_tickets),
            "--plugin-root",
            "/",
            "--cache-root",
            "/",
        ],
        cwd=str(tmp_tickets.parent.parent),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    output = json.loads(completed.stdout)
    assert output["state"] == "escalate"
    assert output["error_code"] == "invalid_doctor_root"


def test_tree_manifest_enforces_scale_limits(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b.txt").write_text("b", encoding="utf-8")

    with pytest.raises(DoctorInputError, match="file count"):
        _tree_manifest(root, max_files=1, max_bytes=100)

    with pytest.raises(DoctorInputError, match="hashed bytes"):
        _tree_manifest(root, max_files=10, max_bytes=1)

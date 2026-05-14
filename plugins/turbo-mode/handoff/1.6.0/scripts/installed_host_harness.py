"""Source-proof installed-host harness primitives."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

try:
    from scripts.storage_primitives import sha256_file
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.storage_primitives import sha256_file  # type: ignore[no-redef]


class InstalledHostHarnessError(RuntimeError):
    pass


def run_source_harness_isolation_proof(
    *,
    source_plugin_root: Path,
    codex_home: Path,
    host_root: Path,
) -> dict[str, object]:
    source_plugin = source_plugin_root.resolve()
    source_checkout = _source_checkout_root(source_plugin)
    isolated_home = codex_home.resolve()
    _reject_real_codex_home(isolated_home)
    installed_plugin = (
        isolated_home / "plugins" / "cache" / "turbo-mode" / "handoff" / "1.6.0"
    )
    if installed_plugin.exists():
        raise InstalledHostHarnessError(
            "source-harness-isolation-proof failed: installed root already exists. "
            f"Got: {str(installed_plugin)!r:.100}"
        )
    installed_plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_plugin,
        installed_plugin,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".venv"),
    )
    host_root.resolve().mkdir(parents=True, exist_ok=True)

    source_manifest = source_plugin / ".codex-plugin" / "plugin.json"
    installed_manifest = installed_plugin / ".codex-plugin" / "plugin.json"
    source_manifest_payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    installed_manifest_payload = json.loads(installed_manifest.read_text(encoding="utf-8"))
    manifest_identity = {
        "name": installed_manifest_payload["name"],
        "version": installed_manifest_payload["version"],
        "source_sha256": sha256_file(source_manifest),
        "installed_sha256": sha256_file(installed_manifest),
    }
    if source_manifest_payload != installed_manifest_payload:
        raise InstalledHostHarnessError(
            "source-harness-isolation-proof failed: manifest payload mismatch. "
            f"Got: {str(installed_manifest)!r:.100}"
        )

    probe_payload = _run_helper_probe(
        installed_plugin=installed_plugin,
        source_checkout=source_checkout,
        host_root=host_root.resolve(),
        codex_home=isolated_home,
    )
    proof = {
        "evidence_label": "source-harness-isolation-proof",
        "install_method": "test-only-copy",
        "install_method_equivalence": "not-equivalent-to-installed-cache-refresh",
        "app_server_installed": False,
        "installed_host_behavior_matrix_exercised": False,
        "source_checkout_root": str(source_checkout),
        "installed_plugin_root": str(installed_plugin.resolve()),
        "manifest_identity": manifest_identity,
        **probe_payload,
    }
    verify_source_harness_payload(proof)
    return proof


def verify_source_harness_payload(payload: dict[str, object]) -> None:
    if payload.get("evidence_label") != "source-harness-isolation-proof":
        raise _invalid_payload("unexpected evidence label", payload.get("evidence_label"))
    if payload.get("install_method") != "test-only-copy":
        raise _invalid_payload("unexpected install method", payload.get("install_method"))
    if payload.get("install_method_equivalence") != "not-equivalent-to-installed-cache-refresh":
        raise _invalid_payload(
            "unexpected install method equivalence",
            payload.get("install_method_equivalence"),
        )
    if payload.get("app_server_installed") is not False:
        raise _invalid_payload(
            "app-server proof is not allowed",
            payload.get("app_server_installed"),
        )
    if payload.get("installed_host_behavior_matrix_exercised") is not False:
        raise _invalid_payload(
            "installed-host behavior proof is not allowed",
            payload.get("installed_host_behavior_matrix_exercised"),
        )

    source_checkout = _payload_path(payload, "source_checkout_root")
    installed_plugin = _payload_path(payload, "installed_plugin_root")
    if installed_plugin.is_relative_to(source_checkout):
        raise _source_leakage("installed plugin root", installed_plugin)

    _require_inside_installed(payload, "resolved_helper_path", installed_plugin, source_checkout)
    _require_inside_installed(payload, "resolved_skill_doc_path", installed_plugin, source_checkout)
    for path in _payload_path_list(payload, "helper_subprocess_command_paths"):
        _require_path_inside_installed(path, installed_plugin, source_checkout)
    for path in _payload_path_list(payload, "loaded_handoff_module_files"):
        _require_path_inside_installed(path, installed_plugin, source_checkout)

    helper_cwd = _payload_path(payload, "helper_process_cwd")
    if helper_cwd.is_relative_to(source_checkout):
        raise _source_leakage("helper process cwd", helper_cwd)
    pythonpath = payload.get("helper_process_pythonpath")
    if isinstance(pythonpath, str) and _path_list_has_source_entry(
        pythonpath.split(os.pathsep),
        source_checkout,
        base=helper_cwd,
    ):
        raise _source_leakage("helper process PYTHONPATH", Path(pythonpath))
    if payload.get("source_checkout_sys_path_entries") not in ([], ()):
        raise _source_leakage("helper process sys.path", Path(str(source_checkout)))
    if _path_list_has_source_entry(
        [str(path) for path in payload.get("helper_process_sys_path", [])],
        source_checkout,
        base=helper_cwd,
    ):
        raise _source_leakage("helper process sys.path", Path(str(source_checkout)))

    identity = payload.get("manifest_identity")
    if not isinstance(identity, dict):
        raise _invalid_payload("missing manifest identity", identity)
    if identity.get("name") != "handoff":
        raise _invalid_payload("unexpected manifest name", identity.get("name"))
    if identity.get("version") != "1.6.0":
        raise _invalid_payload("unexpected manifest version", identity.get("version"))
    if identity.get("source_sha256") != identity.get("installed_sha256"):
        raise _invalid_payload(
            "manifest hash mismatch",
            identity.get("installed_sha256"),
        )


def _run_helper_probe(
    *,
    installed_plugin: Path,
    source_checkout: Path,
    host_root: Path,
    codex_home: Path,
) -> dict[str, object]:
    probe = textwrap.dedent(
        """
        from __future__ import annotations

        import importlib
        import inspect
        import json
        import os
        import sys
        from pathlib import Path

        installed_plugin = Path(sys.argv[1]).resolve()
        source_checkout = Path(sys.argv[2]).resolve()
        cwd = Path.cwd().resolve()

        def is_relative_to(path: Path, root: Path) -> bool:
            try:
                path.relative_to(root)
            except ValueError:
                return False
            return True

        def normalize_path(entry: str) -> Path:
            if entry == "":
                return cwd
            return Path(entry).resolve()

        sys.path = [
            str(installed_plugin),
            *[
                entry
                for entry in sys.path
                if not is_relative_to(normalize_path(entry), source_checkout)
            ],
        ]
        modules = [
            importlib.import_module("scripts.session_state"),
            importlib.import_module("scripts.storage_authority"),
        ]
        sys_path_entries = [str(normalize_path(entry)) for entry in sys.path]
        source_sys_path_entries = [
            entry
            for entry in sys_path_entries
            if is_relative_to(Path(entry), source_checkout)
        ]
        helper_path = installed_plugin / "scripts" / "session_state.py"
        skill_doc_path = installed_plugin / "skills" / "save" / "SKILL.md"
        payload = {
            "resolved_helper_path": str(helper_path.resolve()),
            "resolved_skill_doc_path": str(skill_doc_path.resolve()),
            "helper_subprocess_command_paths": [
                str(helper_path.resolve())
            ],
            "helper_process_cwd": str(cwd),
            "helper_process_pythonpath": os.environ.get("PYTHONPATH"),
            "helper_process_sys_path": sys_path_entries,
            "source_checkout_sys_path_entries": source_sys_path_entries,
            "loaded_handoff_module_files": [
                str(Path(inspect.getfile(module)).resolve())
                for module in modules
            ],
        }
        print(json.dumps(payload, sort_keys=True))
        """
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CODEX_HOME"] = str(codex_home)
    completed = subprocess.run(
        [sys.executable, "-c", probe, str(installed_plugin), str(source_checkout)],
        cwd=host_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise InstalledHostHarnessError(
            "source-harness-isolation-proof failed: helper probe failed. "
            f"Got: {completed.stderr!r:.100}"
        )
    return json.loads(completed.stdout)


def _source_checkout_root(source_plugin_root: Path) -> Path:
    try:
        return source_plugin_root.parents[3].resolve()
    except IndexError as exc:
        raise InstalledHostHarnessError(
            "source-harness-isolation-proof failed: source checkout root unavailable. "
            f"Got: {str(source_plugin_root)!r:.100}"
        ) from exc


def _reject_real_codex_home(codex_home: Path) -> None:
    real_home = (Path.home() / ".codex").resolve()
    if codex_home == real_home or codex_home.is_relative_to(real_home):
        raise InstalledHostHarnessError(
            "source-harness-isolation-proof failed: real CODEX_HOME mutation blocked. "
            f"Got: {str(codex_home)!r:.100}"
        )


def _payload_path(payload: dict[str, object], key: str) -> Path:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise _invalid_payload(f"missing path field {key}", value)
    return Path(value).resolve()


def _payload_path_list(payload: dict[str, object], key: str) -> list[Path]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise _invalid_payload(f"missing path list field {key}", value)
    return [Path(str(path)).resolve() for path in value]


def _require_inside_installed(
    payload: dict[str, object],
    key: str,
    installed_plugin: Path,
    source_checkout: Path,
) -> None:
    _require_path_inside_installed(
        _payload_path(payload, key),
        installed_plugin,
        source_checkout,
    )


def _require_path_inside_installed(
    path: Path,
    installed_plugin: Path,
    source_checkout: Path,
) -> None:
    if path.is_relative_to(source_checkout):
        raise _source_leakage("source checkout leakage", path)
    if not path.is_relative_to(installed_plugin):
        raise _invalid_payload("path is outside installed plugin root", str(path))


def _path_list_has_source_entry(entries: list[str], source_checkout: Path, *, base: Path) -> bool:
    for entry in entries:
        normalized = base if entry == "" else Path(entry).resolve()
        if normalized.is_relative_to(source_checkout):
            return True
    return False


def _source_leakage(context: str, path: Path) -> InstalledHostHarnessError:
    return InstalledHostHarnessError(
        "source-harness-isolation-proof failed: source checkout leakage. "
        f"Got: {context}={str(path)!r:.100}"
    )


def _invalid_payload(reason: str, value: object) -> InstalledHostHarnessError:
    return InstalledHostHarnessError(
        f"source-harness-isolation-proof failed: {reason}. Got: {value!r:.100}"
    )

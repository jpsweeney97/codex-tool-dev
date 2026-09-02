"""Runtime import-boundary tests (ADR-0001 + 2026-07-16 amendment).

Out-of-process by design: the boundary is module-level entrypoint behavior,
so every case drives the real CLI on an isolated copy of the live bundle.
Test code may use py_compile/importlib freely — the identifier ban governs
production sources only.
"""

from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]


def make_bundle(tmp_path: Path) -> Path:
    """Copy the live bundle (scripts/ + references/) into an isolated root."""
    root = tmp_path / "bundle"
    root.mkdir(parents=True)
    shutil.copytree(SKILL_ROOT / "scripts", root / "scripts")
    shutil.copytree(SKILL_ROOT / "references", root / "references")
    return root


def run_cli(
    root: Path, *args: str, tmpdir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the copied entrypoint in a deterministic subprocess."""
    env = dict(os.environ, LC_ALL="C.UTF-8", PYTHONHASHSEED="0")
    if tmpdir is not None:
        env["TMPDIR"] = str(tmpdir)
    return subprocess.run(
        [
            "uv",
            "run",
            "--script",
            str(root / "scripts" / "deliberate-validate.py"),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def identity_args(root: Path) -> list[str]:
    """Cheapest full contract-loading command: hash the contract file itself."""
    data = root / "references" / "contract-data.yaml"
    return ["identity", "--data", str(data), str(data)]


def test_unmodified_bundle_copy_passes(tmp_path: Path) -> None:
    """Harness pilot: the copied bundle loads its contract and exits 0."""
    root = make_bundle(tmp_path)
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 0, result.stderr
    assert "identities:" in result.stdout


def test_contract_missing_import_boundary_is_refused(tmp_path: Path) -> None:
    """A contract without the policy section fails the exact top-level key set."""
    root = make_bundle(tmp_path)
    data = root / "references" / "contract-data.yaml"
    text = data.read_text(encoding="utf-8")
    start = text.index("import-boundary:")
    end = text.index("\n# ", start)
    data.write_text(text[:start] + text[end + 1 :], encoding="utf-8")
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "top-level keys must be exactly" in result.stderr


def test_contract_policy_tamper_is_refused_at_load(tmp_path: Path) -> None:
    """Embedded census policy vs contract section: any drift refuses (ADR-0001)."""
    root = make_bundle(tmp_path)
    data = root / "references" / "contract-data.yaml"
    text = data.read_text(encoding="utf-8")
    assert text.count("[.egg, .whl, .zip]") == 1
    data.write_text(
        text.replace("[.egg, .whl, .zip]", "[.egg, .whl]"), encoding="utf-8"
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "import-boundary" in result.stderr
    assert "archive-suffixes" in result.stderr


def test_prior_contract_data_version_is_refused(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    data = root / "references" / "contract-data.yaml"
    text = data.read_text(encoding="utf-8")
    assert text.count("contract-data-version: 6") == 1
    data.write_text(
        text.replace("contract-data-version: 6", "contract-data-version: 5"),
        encoding="utf-8",
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "unsupported contract-data-version" in result.stderr


def seed_marker_pyc(root: Path, tmp_path: Path, name: str) -> Path:
    """Compile a marker-writing source into a sourceless .pyc under scripts/."""
    marker = tmp_path / "executed.marker"
    src = tmp_path / "seed_src.py"
    src.write_text(f"open({str(marker)!r}, 'w').write('ran')\n", encoding="utf-8")
    py_compile.compile(str(src), cfile=str(root / "scripts" / name))
    return marker


def test_seeded_sourceless_pyc_is_refused_without_executing(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    marker = seed_marker_pyc(root, tmp_path, "_deliberate_hidden.pyc")
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "import boundary refused" in result.stderr
    assert "_deliberate_hidden.pyc" in result.stderr
    assert not marker.exists()


def test_seeded_pycache_directory_is_refused(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    cache = root / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "stale.cpython-313.pyc").write_bytes(b"\x00stale")
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "__pycache__" in result.stderr


def test_symlinked_module_and_symlinked_package_are_refused(tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("VALUE = 1\n", encoding="utf-8")
    outside_pkg = tmp_path / "outside_pkg"
    outside_pkg.mkdir()
    (outside_pkg / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    for label, target, link_name in (
        ("file", outside_file, "_deliberate_link.py"),
        ("package", outside_pkg, "_deliberate_linkpkg"),
    ):
        root = make_bundle(tmp_path / label)
        (root / "scripts" / link_name).symlink_to(target)
        result = run_cli(root, *identity_args(root))
        assert result.returncode == 2, label
        assert "symlink" in result.stderr, label


def test_package_directory_is_refused(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    pkg = root / "scripts" / "_deliberate_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "_deliberate_pkg" in result.stderr


def _zip_bytes(arcname: str = "evilmod.py", body: str = "VALUE = 1\n") -> bytes:
    """A real, structurally valid zip archive (has an end-of-central-directory)."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(arcname, body)
    return buffer.getvalue()


def test_zip_archives_and_disguised_zip_are_refused(tmp_path: Path) -> None:
    """.zip/.egg/.whl fall to the suffix rule; a real (even prefixed) zip with an
    inert suffix falls to pass 2's structural `is_zipfile` check. The `.dat`
    cases use genuine archives: a four-byte fragment would not be importable and
    must not be relied on. `prefixed.dat` is the 2026-07-16 scrutiny case — a
    valid zip behind a shell stub whose first bytes are not `PK`."""
    cases = {
        "payload.zip": b"PK\x03\x04fragment",  # suffix rule; content irrelevant
        "payload.egg": b"PK\x03\x04fragment",
        "payload.whl": b"PK\x03\x04fragment",
        "payload.dat": _zip_bytes(),  # inert suffix: real zip → structural check
        "prefixed.dat": b"#!/bin/sh\n# self-extracting stub\n" + _zip_bytes(),
    }
    for name, content in cases.items():
        root = make_bundle(tmp_path / name.replace(".", "_"))
        (root / "scripts" / name).write_bytes(content)
        result = run_cli(root, *identity_args(root))
        assert result.returncode == 2, name
        assert name in result.stderr, name


def test_nested_python_file_is_refused(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    (root / "scripts" / "fixtures" / "evil.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "evil.py" in result.stderr


def test_stdlib_shadow_is_refused_before_it_can_import(tmp_path: Path) -> None:
    """A scripts/argparse.py would shadow stdlib argparse via sys.path[0]; the
    census must refuse it before the entrypoint's own deferred imports run —
    the marker proves nothing executed."""
    root = make_bundle(tmp_path)
    marker = tmp_path / "shadow.marker"
    (root / "scripts" / "argparse.py").write_text(
        f"open({str(marker)!r}, 'w').write('ran')\n", encoding="utf-8"
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "argparse.py" in result.stderr
    assert not marker.exists()


def test_inert_file_passes_and_conforming_extra_module_is_runtime_inert(
    tmp_path: Path,
) -> None:
    """Layer boundary: the runtime census is layout-only. An inert data file
    passes; a flat conforming-but-uninventoried module also passes at runtime
    (it is unreachable without dynamic import) while the authoring gate
    rejects the same layout via inventory equality."""
    import pytest
    from check_import_closure import check

    root = make_bundle(tmp_path)
    (root / "scripts" / "notes.txt").write_text("plain text\n", encoding="utf-8")
    (root / "scripts" / "_deliberate_extra.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 0, result.stderr
    with pytest.raises(SystemExit, match="on-disk production Python"):
        check(root)


def test_module_name_grammar_matches_declared_pattern(tmp_path: Path) -> None:
    """The census's re-free name check must agree with module-name-pattern."""
    accepted = ["_deliberate_probe.py", "_deliberate_a9_x.py"]
    refused = [
        "_deliberate_.py",
        "_deliberate_9x.py",
        "_Deliberate_x.py",
        "_deliberate_X.py",
        "deliberate_x.py",
        "_deliberate_x.mod.py",
    ]
    for index, name in enumerate(accepted):
        root = make_bundle(tmp_path / f"ok{index}")
        (root / "scripts" / name).write_text("VALUE = 1\n", encoding="utf-8")
        assert run_cli(root, *identity_args(root)).returncode == 0, name
    for index, name in enumerate(refused):
        root = make_bundle(tmp_path / f"bad{index}")
        (root / "scripts" / name).write_text("VALUE = 1\n", encoding="utf-8")
        result = run_cli(root, *identity_args(root))
        assert result.returncode == 2, name
        assert name in result.stderr


def test_cache_prefix_is_external_private_retired_and_unsafe_roots_refuse(
    tmp_path: Path,
) -> None:
    """An external temp root works; any protected-tree placement refuses.

    ADR-0001 requires the prefix outside the repository, not merely outside
    scripts/. The runtime finds the outermost containing Git root (so an inner
    marker cannot narrow the boundary), falls back to the served bundle when
    standalone, resolves symlinks, and refuses before any first-party import.
    The optional shared-module marker becomes active after Task 4 without
    changing this Task-3 checkpoint.
    """
    root = make_bundle(tmp_path / "external")
    scoped = tmp_path / "scoped-tmp"
    scoped.mkdir()
    result = run_cli(root, *identity_args(root), tmpdir=scoped)
    assert result.returncode == 0, result.stderr
    assert list(scoped.glob("deliberate-pycache-*")) == []  # prefix retired at exit
    assert list(root.rglob("deliberate-pycache-*")) == []
    assert list((root / "scripts").rglob("__pycache__")) == []
    assert list((root / "scripts").rglob("*.pyc")) == []

    cases: list[tuple[str, Path, Path]] = []
    for label, relative in (
        ("bundle", "tmp"),
        ("scripts", "scripts"),
        ("allowed-data", "scripts/fixtures"),
    ):
        case_root = make_bundle(tmp_path / label)
        unsafe = case_root / relative
        unsafe.mkdir(parents=True, exist_ok=True)
        cases.append((label, case_root, unsafe))

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    repo_root = make_bundle(repo / "skills" / "deliberate")
    (repo_root / ".git").mkdir()  # inner marker must not narrow the outer root
    repo_tmp = repo / "tmp"  # inside Git root, outside the served bundle
    repo_tmp.mkdir()
    cases.append(("repo", repo_root, repo_tmp))

    link_root = make_bundle(tmp_path / "symlink")
    link_target = link_root / "tmp"
    link_target.mkdir()
    unsafe_link = tmp_path / "symlink" / "tmp-link"
    unsafe_link.symlink_to(link_target, target_is_directory=True)
    cases.append(("symlink", link_root, unsafe_link))

    for label, case_root, unsafe in cases:
        marker = tmp_path / f"{label}.marker"
        shared = case_root / "scripts" / "_deliberate_shared.py"
        if shared.exists():
            text = shared.read_text(encoding="utf-8")
            needle = "from __future__ import annotations\n"
            assert text.count(needle) == 1
            shared.write_text(
                text.replace(
                    needle,
                    needle + f"\nopen({str(marker)!r}, 'w').write('ran')\n",
                    1,
                ),
                encoding="utf-8",
            )
        result = run_cli(case_root, *identity_args(case_root), tmpdir=unsafe)
        assert result.returncode == 2, label
        assert "cache temp root must resolve outside" in result.stderr, label
        assert not marker.exists(), label
        assert list(tmp_path.rglob("deliberate-pycache-*")) == [], label
        assert list(tmp_path.rglob("*.pyc")) == [], label
        assert list((case_root / "scripts").rglob("__pycache__")) == [], label
        assert list((case_root / "scripts").rglob("*.pyc")) == [], label


def test_case_aliased_repo_tmp_refuses(tmp_path: Path) -> None:
    """The case-aliased spelling of a temp root inside the Git root must refuse
    like its canonical twin. Constructible only on a case-insensitive
    filesystem; elsewhere it must skip visibly, never vanish silently from the
    case list."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    repo_root = make_bundle(repo / "skills" / "deliberate")
    (repo_root / ".git").mkdir()  # inner marker must not narrow the outer root
    repo_tmp = repo / "tmp"
    repo_tmp.mkdir()
    case_alias = repo.parent / repo.name.swapcase() / "tmp"
    if not (case_alias.exists() and os.path.samefile(case_alias, repo_tmp)):
        pytest.skip("case-aliased path unconstructible: filesystem is case-sensitive")
    marker = tmp_path / "case-alias.marker"
    shared = repo_root / "scripts" / "_deliberate_shared.py"
    text = shared.read_text(encoding="utf-8")
    needle = "from __future__ import annotations\n"
    assert text.count(needle) == 1
    shared.write_text(
        text.replace(
            needle,
            needle + f"\nopen({str(marker)!r}, 'w').write('ran')\n",
            1,
        ),
        encoding="utf-8",
    )
    result = run_cli(repo_root, *identity_args(repo_root), tmpdir=case_alias)
    assert result.returncode == 2
    assert "cache temp root must resolve outside" in result.stderr
    assert not marker.exists()
    assert list(tmp_path.rglob("deliberate-pycache-*")) == []
    assert list(tmp_path.rglob("*.pyc")) == []
    assert list((repo_root / "scripts").rglob("__pycache__")) == []
    assert list((repo_root / "scripts").rglob("*.pyc")) == []


def test_sourceless_shadow_of_shared_module_is_refused(tmp_path: Path) -> None:
    """A sourceless _deliberate_shared.pyc beside the real module is exactly
    the directly-read-bytecode hazard: refused before any import."""
    root = make_bundle(tmp_path)
    marker = seed_marker_pyc(root, tmp_path, "_deliberate_shared.pyc")
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "_deliberate_shared.pyc" in result.stderr
    assert not marker.exists()


def test_second_invocation_never_reuses_prior_bytecode(tmp_path: Path) -> None:
    """Gate-1 follow-up hazard as a tripwire: after a same-size, mtime-restored
    edit to _deliberate_shared.py, the second invocation must execute the
    edited code — a reused cache entry (size+mtime match) would show the old
    string. The observable channel is safe_parse's anchor refusal, which lives
    in the shared module."""
    root = make_bundle(tmp_path)
    scoped = tmp_path / "scoped-tmp"
    scoped.mkdir()
    bad_contract = tmp_path / "anchored.yaml"
    bad_contract.write_text("a: &x 1\nb: *x\n", encoding="utf-8")
    probe_args = ["identity", "--data", str(bad_contract), str(bad_contract)]
    first = run_cli(root, *probe_args, tmpdir=scoped)
    assert first.returncode == 2
    assert "YAML anchors are rejected" in first.stderr
    shared = root / "scripts" / "_deliberate_shared.py"
    before = shared.stat()
    text = shared.read_text(encoding="utf-8")
    assert text.count("YAML anchors are rejected") == 1
    edited = text.replace("YAML anchors are rejected", "YAML anchorZ are rejected")
    assert len(edited.encode("utf-8")) == len(text.encode("utf-8"))
    shared.write_text(edited, encoding="utf-8")
    os.utime(shared, ns=(before.st_atime_ns, before.st_mtime_ns))
    second = run_cli(root, *probe_args, tmpdir=scoped)
    assert second.returncode == 2
    assert "YAML anchorZ are rejected" in second.stderr


def test_unreadable_inert_file_is_refused(tmp_path: Path) -> None:
    """Pass 2 must refuse an inert file it cannot read (2026-07-16 v6
    implementation-review finding F2): is_zipfile swallows OSError into
    False, which would let an unreadable disguised zip pass — unverifiable
    content is unsafe, matching the containment check's posture."""
    root = make_bundle(tmp_path)
    hidden = root / "scripts" / "hidden.dat"
    hidden.write_bytes(b"#!/bin/sh\n# stub\n" + _zip_bytes())
    hidden.chmod(0)
    try:
        result = run_cli(root, *identity_args(root))
    finally:
        hidden.chmod(0o644)
    assert result.returncode == 2
    assert "hidden.dat" in result.stderr
    assert "could not be read" in result.stderr


def test_nested_conforming_module_is_refused_by_the_flat_rule(tmp_path: Path) -> None:
    """Isolates the flat-placement rule (2026-07-16 v6 implementation-review
    finding F3): a conforming module name nested under the data allowlist
    trips only the flat rule — the existing nested test's evil.py also trips
    the naming rule, so a mutant with the flat rule disabled survived it."""
    root = make_bundle(tmp_path)
    (root / "scripts" / "fixtures" / "_deliberate_evil.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "_deliberate_evil.py" in result.stderr
    assert "must be flat" in result.stderr


def test_scripts_directory_symlink_is_refused(tmp_path: Path) -> None:
    """scripts/ itself must be a real directory (census precondition; the
    refusal existed untested — 2026-07-16 v6 implementation-review F3)."""
    root = make_bundle(tmp_path)
    real_scripts = tmp_path / "real-scripts"
    (root / "scripts").rename(real_scripts)
    (root / "scripts").symlink_to(real_scripts, target_is_directory=True)
    result = run_cli(root, *identity_args(root))
    assert result.returncode == 2
    assert "must be a real directory" in result.stderr

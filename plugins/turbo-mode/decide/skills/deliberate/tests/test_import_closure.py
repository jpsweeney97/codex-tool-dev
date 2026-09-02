"""Gate-2 checker tests: synthetic layouts prove detection; the live tree must pass.

The checker is non-executing by contract, so these tests exercise it against
throwaway skill layouts on disk — never by importing production code.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import yaml

from check_import_closure import check, import_closure


def _zip_bytes(arcname: str = "evilmod.py", body: str = "VALUE = 1\n") -> bytes:
    """A real, structurally valid zip archive (has an end-of-central-directory)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(arcname, body)
    return buffer.getvalue()

SKILL_ROOT = Path(__file__).resolve().parents[1]

LIVE_POLICY: dict = yaml.safe_load(
    (SKILL_ROOT / "references" / "contract-data.yaml").read_text(encoding="utf-8")
)["import-boundary"]


def make_layout(
    root: Path,
    entry_body: str,
    modules: dict[str, str],
    surfaces: list[str],
    policy: dict | None = None,
) -> Path:
    """Write a minimal skill layout: entrypoint, modules, contract data.

    Module keys are scripts-relative paths; nested keys create the parent
    directories so package layouts can be expressed (to prove rejection).
    Every layout carries an import-boundary section (default: the live
    policy) because the checker consumes the contract as its policy source.
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "deliberate-validate.py").write_text(entry_body, encoding="utf-8")
    for name, body in modules.items():
        target = scripts / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    references = root / "references"
    references.mkdir()
    document = {
        "validation": {"method-surfaces": surfaces},
        "import-boundary": policy if policy is not None else LIVE_POLICY,
    }
    (references / "contract-data.yaml").write_text(
        yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
    )
    return root


def test_exact_closure_passes_and_ignores_external_imports(tmp_path: Path) -> None:
    """Sibling, transitive, and function-scoped imports count; stdlib does not."""
    root = make_layout(
        tmp_path,
        "import os\nimport yaml\nimport _deliberate_shared\n",
        {
            "_deliberate_shared.py": (
                "def load():\n    import _deliberate_util\n    return _deliberate_util\n"
            ),
            "_deliberate_util.py": "VALUE = 1\n",
        },
        [
            "SKILL.md",
            "scripts/deliberate-validate.py",
            "scripts/_deliberate_shared.py",
            "scripts/_deliberate_util.py",
        ],
    )
    message = check(root)
    assert message == (
        "import closure, on-disk production files, and method-surfaces "
        "agree: 3 Python surface(s)"
    )


def test_omitted_module_is_detected(tmp_path: Path) -> None:
    """A module the entrypoint reaches but the inventory omits must fail."""
    root = make_layout(
        tmp_path,
        "import _deliberate_shared\n",
        {
            "_deliberate_shared.py": "import _deliberate_util\n",
            "_deliberate_util.py": "VALUE = 1\n",
        },
        ["scripts/deliberate-validate.py", "scripts/_deliberate_shared.py"],
    )
    with pytest.raises(
        SystemExit, match=r"Imported but not inventoried.*_deliberate_util"
    ):
        check(root)


def test_unimported_inventory_entry_is_detected(tmp_path: Path) -> None:
    """A pinned Python surface nothing imports must fail (dead inventory)."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {"_deliberate_ghost.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py", "scripts/_deliberate_ghost.py"],
    )
    with pytest.raises(
        SystemExit, match=r"inventoried but never imported.*_deliberate_ghost"
    ):
        check(root)


def test_uninventoried_shadowing_module_is_detected(tmp_path: Path) -> None:
    """A local file taking a dependency's name violates the naming rule."""
    root = make_layout(
        tmp_path,
        "import yaml\n",
        {"yaml.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"must match _deliberate_<domain>\.py.*yaml\.py"
    ):
        check(root)


def test_inventoried_shadowing_module_is_detected(tmp_path: Path) -> None:
    """Inventorying the shadow file must not launder it past the naming rule."""
    root = make_layout(
        tmp_path,
        "import yaml\n",
        {"yaml.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py", "scripts/yaml.py"],
    )
    with pytest.raises(
        SystemExit, match=r"must match _deliberate_<domain>\.py.*yaml\.py"
    ):
        check(root)


def test_dynamic_import_call_is_rejected(tmp_path: Path) -> None:
    """__import__ can execute first-party code the static closure never sees."""
    root = make_layout(
        tmp_path,
        '__import__("_deliberate_hidden")\n',
        {"_deliberate_hidden.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*__import__"
    ):
        check(root)


def test_importlib_import_is_rejected(tmp_path: Path) -> None:
    """importlib is dynamic-import machinery regardless of how it is imported."""
    root = make_layout(
        tmp_path,
        "from importlib import import_module\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*importlib"
    ):
        check(root)


def test_package_submodule_layout_is_rejected(tmp_path: Path) -> None:
    """A package under scripts/ executes files the flat closure cannot pin."""
    root = make_layout(
        tmp_path,
        "import _deliberate_pkg.sub\n",
        {
            "_deliberate_pkg/__init__.py": "",
            "_deliberate_pkg/sub.py": "VALUE = 1\n",
        },
        [
            "scripts/deliberate-validate.py",
            "scripts/_deliberate_pkg/__init__.py",
        ],
    )
    with pytest.raises(SystemExit, match=r"directories under scripts/ are forbidden"):
        check(root)


def test_dotted_first_party_import_is_rejected(tmp_path: Path) -> None:
    """A dotted first-party import has no meaning for flat production modules."""
    root = make_layout(
        tmp_path,
        "import _deliberate_shared.sub\n",
        {"_deliberate_shared.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py", "scripts/_deliberate_shared.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dotted import of a first-party module is unsupported"
    ):
        check(root)


def test_on_disk_orphan_module_is_detected(tmp_path: Path) -> None:
    """A conforming on-disk module outside closure and inventory must fail.

    This is the fail-closed backstop: any first-party file reachable only
    dynamically (or plain dead code) surfaces as an on-disk/inventory delta.
    """
    root = make_layout(
        tmp_path,
        "import os\n",
        {"_deliberate_orphan.py": "VALUE = 1\n"},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"On disk but not inventoried.*_deliberate_orphan"
    ):
        check(root)


def test_relative_import_fails_fast(tmp_path: Path) -> None:
    """Relative imports have no meaning in the script-directory layout."""
    root = make_layout(
        tmp_path,
        "from . import anything\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(SystemExit, match=r"relative import is unsupported"):
        check(root)


def test_sourceless_bytecode_artifact_is_rejected(tmp_path: Path) -> None:
    """A stray .pyc under scripts/ is executable and must fail the census.

    Reproduces the 2026-07-15 re-review bypass: sourceless bytecode loads
    through SourcelessFileLoader regardless of any cache prefix.
    """
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "_deliberate_hidden.pyc").write_bytes(b"\x00fake-bytecode")
    with pytest.raises(SystemExit, match=r"importable non-source artifact"):
        check(root)


def test_extension_module_artifact_is_rejected(tmp_path: Path) -> None:
    """An extension module (.so) is loadable code without hashed source."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "_deliberate_fast.so").write_bytes(b"\x00fake-extension")
    with pytest.raises(SystemExit, match=r"importable non-source artifact"):
        check(root)


def test_pycache_directory_is_rejected(tmp_path: Path) -> None:
    """A __pycache__ under scripts/ holds bytecode that shadows hashed source."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    cache = root / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "x.cpython-313.pyc").write_bytes(b"\x00fake-bytecode")
    with pytest.raises(SystemExit, match=r"__pycache__ is forbidden"):
        check(root)


def test_symlinked_package_is_rejected(tmp_path: Path) -> None:
    """A symlinked package imports and executes external code.

    Reproduces the 2026-07-15 re-review bypass: rglob("*.py") never
    traverses the symlink target, so the old census missed it entirely.
    """
    external = tmp_path / "external_pkg"
    external.mkdir()
    (external / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    root = make_layout(
        tmp_path / "skill",
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "_deliberate_pkg").symlink_to(
        external, target_is_directory=True
    )
    with pytest.raises(SystemExit, match=r"symlinks are forbidden"):
        check(root)


def test_symlinked_module_file_is_rejected(tmp_path: Path) -> None:
    """A symlinked .py resolves outside the tree the census hashed."""
    external = tmp_path / "real_module.py"
    external.write_text("VALUE = 1\n", encoding="utf-8")
    root = make_layout(
        tmp_path / "skill",
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "_deliberate_shared.py").symlink_to(external)
    with pytest.raises(SystemExit, match=r"symlinks are forbidden"):
        check(root)


def test_unexpected_directory_is_rejected(tmp_path: Path) -> None:
    """Any directory outside the declared data allowlist is a package form."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "helpers").mkdir()
    with pytest.raises(SystemExit, match=r"directories under scripts/ are forbidden"):
        check(root)


def test_allowed_data_directory_and_inert_files_pass(tmp_path: Path) -> None:
    """The declared data allowlist and loader-suffix-free files stay legal."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    cases = root / "scripts" / "fixtures" / "must-pass"
    cases.mkdir(parents=True)
    (cases / "case.yaml").write_text("k: v\n", encoding="utf-8")
    (root / "scripts" / ".DS_Store").write_bytes(b"\x00")
    message = check(root)
    assert message.endswith("1 Python surface(s)")


def test_python_inside_data_directory_is_rejected(tmp_path: Path) -> None:
    """The data allowlist never launders nested Python past the flat rule."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    fixtures = root / "scripts" / "fixtures"
    fixtures.mkdir()
    (fixtures / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"packages and nested files are forbidden"):
        check(root)


def test_import_resolving_to_sourceless_bytecode_is_rejected(tmp_path: Path) -> None:
    """Discovery itself must refuse an import satisfied only by bytecode.

    Exercises the closure layer directly (no census): the 2026-07-15 bypass
    classified `import _deliberate_hidden` as third-party because only
    `<name>.py` counted as first-party evidence.
    """
    root = make_layout(
        tmp_path,
        "import _deliberate_hidden\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    scripts = root / "scripts"
    (scripts / "_deliberate_hidden.pyc").write_bytes(b"\x00fake-bytecode")
    from check_import_closure import BoundaryPolicy

    policy = BoundaryPolicy(LIVE_POLICY, root / "references" / "contract-data.yaml")
    with pytest.raises(SystemExit, match=r"never bytecode, a package, or a symlink"):
        import_closure(root / "scripts" / "deliberate-validate.py", policy)


def test_import_resolving_to_directory_is_rejected(tmp_path: Path) -> None:
    """Even an allowlisted data directory must never be importable."""
    root = make_layout(
        tmp_path,
        "import fixtures\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "fixtures").mkdir()
    from check_import_closure import BoundaryPolicy

    policy = BoundaryPolicy(LIVE_POLICY, root / "references" / "contract-data.yaml")
    with pytest.raises(SystemExit, match=r"never bytecode, a package, or a symlink"):
        import_closure(root / "scripts" / "deliberate-validate.py", policy)


def test_builtins_import_alias_is_rejected(tmp_path: Path) -> None:
    """`from builtins import __import__ as x` is dynamic import by alias.

    Exact 2026-07-15 re-review probe: the old checker matched only an AST
    Name spelled __import__ and passed this form.
    """
    root = make_layout(
        tmp_path,
        'from builtins import __import__ as dynamic_import\ndynamic_import("os")\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*builtins"
    ):
        check(root)


def test_builtins_attribute_import_is_rejected(tmp_path: Path) -> None:
    """`builtins.__import__(...)` is dynamic import by attribute access.

    Exact 2026-07-15 re-review probe.
    """
    root = make_layout(
        tmp_path,
        'import builtins\nbuiltins.__import__("os")\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*builtins"
    ):
        check(root)


def test_exec_identifier_is_rejected(tmp_path: Path) -> None:
    """exec/eval/compile can construct imports the static closure never sees."""
    root = make_layout(
        tmp_path,
        'exec("import _deliberate_hidden")\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*exec"
    ):
        check(root)


def test_zipimport_reference_is_rejected(tmp_path: Path) -> None:
    """zipimport loads code from an archive the static closure never sees.

    Reproduces the 2026-07-15 review-reviewer bypass: the entrypoint imported
    zipimport and executed a module from a `.zip`; zipimport was absent from
    the ban and `.zip` absent from the census, so the gate passed green.
    """
    root = make_layout(
        tmp_path,
        'import zipimport\nzipimport.zipimporter("payload.zip").load_module("evil")\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(
        SystemExit, match=r"dynamic import machinery is forbidden.*zipimport"
    ):
        check(root)


def test_zip_archive_artifact_is_rejected(tmp_path: Path) -> None:
    """A `.zip` beside the modules is loadable via zipimport and must fail the census.

    Defense in depth for the zipimport bypass: the archive is rejected on disk
    even when no source references zipimport.
    """
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "payload.zip").write_bytes(b"PK\x03\x04fake-archive")
    with pytest.raises(SystemExit, match=r"importable non-source artifact"):
        check(root)


def test_disguised_zip_archive_is_rejected(tmp_path: Path) -> None:
    """A zip with an inert suffix still imports via sys.path + zipimport hook.

    Reproduces the follow-up bypass found while verifying the narrowed ban:
    `payload.dat` (real zip) added to sys.path loads `import evilmod` with no
    banned identifier named. Structural zip detection closes it, keeping the
    census guarantee that justifies the narrowed identifier ban.
    """
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "payload.dat").write_bytes(_zip_bytes())
    with pytest.raises(
        SystemExit, match=r"valid zip archive despite an inert suffix"
    ):
        check(root)


def test_prefixed_zip_archive_is_rejected(tmp_path: Path) -> None:
    """A valid zip carrying an arbitrary prefix (first bytes not ``PK``) is caught.

    Regression for the 2026-07-16 scrutiny finding: a four-byte magic sniff
    reads only offset 0, so a shell/self-extracting stub prepended to a real
    zip passed the census green while zipimport still loaded a module from it.
    zipimport locates the archive from its trailing end-of-central-directory
    record, so a structural check must too.
    """
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    prefix = b"#!/bin/sh\n# self-extracting stub; bytes below are a real zip\n"
    payload = prefix + _zip_bytes()
    assert payload[:4] != b"PK\x03\x04"
    (root / "scripts" / "payload.dat").write_bytes(payload)
    with pytest.raises(
        SystemExit, match=r"valid zip archive despite an inert suffix"
    ):
        check(root)


def test_inert_non_archive_file_still_passes(tmp_path: Path) -> None:
    """A genuinely inert file (no loadable suffix, no zip magic) is allowed."""
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    (root / "scripts" / "notes.txt").write_bytes(b"plain text, not an archive\n")
    (root / "scripts" / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    assert check(root).endswith("1 Python surface(s)")


def test_wheel_and_egg_archives_are_rejected(tmp_path: Path) -> None:
    """`.whl` and `.egg` are zip-format archives loadable as code."""
    for suffix in (".whl", ".egg"):
        root = make_layout(
            tmp_path / suffix.strip("."),
            "import os\n",
            {},
            ["scripts/deliberate-validate.py"],
        )
        (root / "scripts" / f"payload{suffix}").write_bytes(b"PK\x03\x04fake")
        with pytest.raises(SystemExit, match=r"importable non-source artifact"):
            check(root)


def test_re_compile_attribute_is_allowed(tmp_path: Path) -> None:
    """`re.compile` is ordinary code, not dynamic-import machinery.

    Guards against the over-broad ban that rejected benign attribute access.
    """
    root = make_layout(
        tmp_path,
        'import re\nPATTERN = re.compile(r"[a-z]+")\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    assert check(root).endswith("1 Python surface(s)")


def test_method_named_compile_is_allowed(tmp_path: Path) -> None:
    """A method or attribute named `compile`/`eval`/`exec` is not machinery."""
    root = make_layout(
        tmp_path,
        "class C:\n    def compile(self):\n        return 1\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    assert check(root).endswith("1 Python surface(s)")


def test_banned_word_in_prose_is_allowed(tmp_path: Path) -> None:
    """Banned names as English words in a docstring or string are not rejected."""
    root = make_layout(
        tmp_path,
        '"""We eval nothing; do not exec or compile here."""\n'
        'MSG = "could not compile the report"\n',
        {},
        ["scripts/deliberate-validate.py"],
    )
    assert check(root).endswith("1 Python surface(s)")


def test_live_tree_passes_with_shared_module_closure() -> None:
    """v6 reality: the closure is the entrypoint plus _deliberate_shared."""
    from check_import_closure import BoundaryPolicy

    entrypoint = SKILL_ROOT / "scripts" / "deliberate-validate.py"
    shared = SKILL_ROOT / "scripts" / "_deliberate_shared.py"
    policy = BoundaryPolicy(
        LIVE_POLICY, SKILL_ROOT / "references" / "contract-data.yaml"
    )
    assert import_closure(entrypoint, policy) == {
        entrypoint.resolve(),
        shared.resolve(),
    }
    message = check(SKILL_ROOT)
    assert message == (
        "import closure, on-disk production files, and method-surfaces "
        "agree: 2 Python surface(s)"
    )


def test_live_policy_floor_holds_known_hazard_classes() -> None:
    """Regression floor: single-sourcing must never silently weaken the policy."""
    assert LIVE_POLICY["entrypoint"] == "deliberate-validate.py"
    assert LIVE_POLICY["module-name-pattern"] == r"^_deliberate_[a-z][a-z0-9_]*\.py$"
    assert set(LIVE_POLICY["allowed-data-dirs"]) == {"fixtures"}
    for suffix in (".pyc", ".pyo", ".pyd", ".pyw", ".so"):
        assert suffix in LIVE_POLICY["forbidden-loader-suffixes"]
    assert set(LIVE_POLICY["archive-suffixes"]) == {".egg", ".whl", ".zip"}
    for name in (
        "__import__",
        "__builtins__",
        "builtins",
        "importlib",
        "zipimport",
        "runpy",
        "exec",
        "eval",
        "compile",
    ):
        assert name in LIVE_POLICY["banned-identifiers"]


def test_checker_consumes_the_contract_policy_not_constants(tmp_path: Path) -> None:
    """Weakening a synthetic layout's policy must change checker behavior: the
    contract is the authority, not hardcoded constants. (On the live tree the
    floor test above plus the release-time embedded-vs-contract equality test
    guard against weakening.)

    Weaken `allowed-data-dirs` — a value the checker cannot reconstruct from the
    interpreter (unlike loader suffixes, which the checker re-unions from
    `importlib.machinery.all_suffixes()`, or zips, which it detects
    structurally). With `vendor` allowed, a `scripts/vendor/` directory passes;
    under the live policy the same directory is rejected."""
    weakened = dict(LIVE_POLICY)
    weakened["allowed-data-dirs"] = ["fixtures", "vendor"]
    root = make_layout(
        tmp_path,
        "import os\n",
        {},
        ["scripts/deliberate-validate.py"],
        policy=weakened,
    )
    (root / "scripts" / "vendor").mkdir()
    assert check(root).endswith("1 Python surface(s)")


def test_embedded_runtime_policy_matches_contract_section() -> None:
    """Release-time authentication of the embedded census policy (ADR-0001,
    2026-07-16 amendment): the entrypoint's `_BOUNDARY_POLICY` must equal the
    contract's `import-boundary` section minus `banned-identifiers`. A desynced
    pair cannot ship green, which is what lets `_require_boundary_match` run
    post-import as defense-in-depth rather than as the authentication gate.
    Extraction is non-executing: the entrypoint runs its census on import, so
    the dict is read by AST/`literal_eval`, never by importing production code.
    """
    import ast

    entrypoint = SKILL_ROOT / "scripts" / "deliberate-validate.py"
    tree = ast.parse(entrypoint.read_text(encoding="utf-8"))
    embedded = None
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(
            node.targets[0], ast.Name
        ):
            target = node.targets[0].id
        if target == "_BOUNDARY_POLICY":
            embedded = ast.literal_eval(node.value)
            break
    assert embedded is not None, "_BOUNDARY_POLICY not found in the entrypoint"
    expected = {k: v for k, v in LIVE_POLICY.items() if k != "banned-identifiers"}
    assert embedded == expected


def test_runtime_name_predicate_matches_contract_regex() -> None:
    """The entrypoint's re-free `_boundary_module_name_conforms` must agree with
    the contract's `module-name-pattern` over a generated corpus of realistic
    (newline-free) filenames. Non-executing: the function is dependency-free,
    extracted by source segment and exec'd in isolation, never by importing
    production code. Scope note: `re`'s `$` matches before a trailing newline
    while the predicate requires `.endswith('.py')`, so a name like
    `"_deliberate_x.py\\n"` would disagree — but that class is unreachable
    because both the runtime census and the Gate-2 checker gate on
    `lower.endswith('.py')` before applying the name rule (fail-closed either
    way), so the corpus is deliberately newline-free."""
    import ast
    import itertools
    import re as _re

    source = (SKILL_ROOT / "scripts" / "deliberate-validate.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    func_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_boundary_module_name_conforms"
    )
    namespace: dict = {}
    exec(ast.get_source_segment(source, func_node), namespace)
    predicate = namespace["_boundary_module_name_conforms"]
    regex = _re.compile(LIVE_POLICY["module-name-pattern"])
    corpus = [
        "_deliberate_" + "".join(combo) + ".py"
        for length in range(0, 4)
        for combo in itertools.product("az9_.AZ-", repeat=length)
    ]
    corpus += [
        "_deliberate_shared.py", "_deliberate_a9_x.py", "_deliberate_.py",
        "_deliberate_9x.py", "_Deliberate_x.py", "_deliberate_X.py",
        "deliberate_x.py", "_deliberate_x.mod.py", "_deliberate_shared.txt",
        "deliberate-validate.py", "evil.py", "",
    ]
    for name in corpus:
        assert predicate(name) == bool(regex.match(name)), name


def test_malformed_policy_values_refuse_instead_of_failing_open() -> None:
    """Type-confused policy values must refuse, not degrade (2026-07-16 v6
    implementation-review finding F1): a scalar string in a list-valued key
    turns frozenset() into character-set semantics and silently disables the
    rule it renders, so BoundaryPolicy validates value types fail-closed."""
    from check_import_closure import BoundaryPolicy

    source = SKILL_ROOT / "references" / "contract-data.yaml"
    cases = [
        ("banned-identifiers", "__import__, importlib, exec"),
        ("allowed-data-dirs", "fixtures"),
        ("forbidden-loader-suffixes", ".pyc"),
        ("archive-suffixes", ".zip"),
        ("banned-identifiers", []),
        ("banned-identifiers", ["exec", 3]),
        ("allowed-data-dirs", [""]),
        ("entrypoint", 5),
        ("entrypoint", ""),
        ("module-name-pattern", ["^x$"]),
    ]
    for key, bad in cases:
        broken = dict(LIVE_POLICY)
        broken[key] = bad
        with pytest.raises(SystemExit, match=f"import-boundary {key} must"):
            BoundaryPolicy(broken, source)


def test_invalid_module_name_regex_refuses() -> None:
    from check_import_closure import BoundaryPolicy

    broken = dict(LIVE_POLICY)
    broken["module-name-pattern"] = "["
    with pytest.raises(SystemExit, match="not a valid regular expression"):
        BoundaryPolicy(broken, SKILL_ROOT / "references" / "contract-data.yaml")


def test_checker_consumes_the_contract_ban_list(tmp_path: Path) -> None:
    """Binding coverage for a second policy key (review finding F1): the ban
    list must come from the contract, not constants. An entrypoint naming
    `exec` passes under a synthetic policy whose ban list omits it and is
    rejected under the live policy."""
    weakened = dict(LIVE_POLICY)
    weakened["banned-identifiers"] = ["__import__"]
    root = make_layout(
        tmp_path / "weakened",
        "exec\n",
        {},
        ["scripts/deliberate-validate.py"],
        policy=weakened,
    )
    assert check(root).endswith("1 Python surface(s)")
    strict = make_layout(
        tmp_path / "strict",
        "exec\n",
        {},
        ["scripts/deliberate-validate.py"],
    )
    with pytest.raises(SystemExit, match="dynamic import machinery"):
        check(strict)


def test_unreadable_inert_file_fails_the_check(tmp_path: Path) -> None:
    """Checker-side twin of the runtime unreadable-inert refusal (2026-07-16
    v6 implementation-review finding F2): the two consumers must not drift
    on the unreadable edge."""
    root = make_layout(tmp_path, "import os\n", {}, ["scripts/deliberate-validate.py"])
    hidden = root / "scripts" / "hidden.dat"
    hidden.write_bytes(b"#!/bin/sh\nplain stub, no archive")
    hidden.chmod(0)
    try:
        with pytest.raises(SystemExit, match="could not be read"):
            check(root)
    finally:
        hidden.chmod(0o644)

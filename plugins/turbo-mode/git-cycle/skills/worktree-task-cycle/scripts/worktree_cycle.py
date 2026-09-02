#!/usr/bin/env python3
"""Guarded lifecycle verbs for persistent-satellite worktrees.

Single-sourced machinery for the `worktree-task-cycle` skill (git-cycle
plugin). Every verb re-derives its facts from git at call time; the only
state this script owns is lease directories and validation records under
`<git-common-dir>/skill-worktree/`.

Output contract (the calling agent branches on labeled lines, not prose):
`FACT:` / `PROOF:` / `POLICY:` / `STATE:` / `REFUSE:` lines, then a final
`RESULT: ok` or `RESULT: refused`. Exit codes: 0 = verb completed with all
proofs green; 2 = refusal or hard stop (labeled reason on stdout); 1 =
unexpected error.

`inspect` also emits pinned machine facts for fleet callers:
`FACT: lock=canonical|noncanonical|absent`,
`FACT: lease=absent|self|foreign|unreadable|scope-mismatch`, and
`FACT: lease-purpose=none|task|fleet|unknown`. The helper-owned
`fleet-lease-acquire` / `fleet-lease-release` verbs serialize repo-owned fleet
mutations without teaching callers the owner-record schema; release succeeds
only from a verified healthy, decommissioned, or bare terminal.

This script never performs: breaking a foreign lease, `branch -D`,
`worktree remove`, any force flag, push/publish, orphan adoption or
discard. It prints facts and refuses; user-authorized destructive
recovery is run by the agent in the visible transcript.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MIN_PYTHON = (3, 9)
CANONICAL_LOCK_REASON = "parked skill workspace (permanent)"
SILENT_IGNORED_BASENAMES = frozenset({".DS_Store"})
REPORT_IGNORED_SEGMENTS = frozenset(
    {"__pycache__", ".venv", ".pytest_cache", ".ruff_cache", ".plugin-eval"}
)
REPORT_IGNORED_PREFIXES = (".agents/handoffs/", ".agents/scratch/", ".claude/")
OP_MARKERS = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
)
ENV_IDENTITIES = (
    ("CLAUDE_CODE_SESSION_ID", "claude-code"),
    ("CODEX_THREAD_ID", "codex"),
)


def say(label: str, message: str) -> None:
    print(f"{label}: {message}")


def fact(message: str) -> None:
    say("FACT", message)


def proof(message: str) -> None:
    say("PROOF", message)


def policy(message: str) -> None:
    say("POLICY", message)


_CLEANUPS: "list" = []


def _run_cleanups() -> "list[str]":
    # a failed cleanup must not mask a refusal already in flight; on a verb's
    # ok path the caller must check the returned failures before claiming ok
    failures: "list[str]" = []
    while _CLEANUPS:
        callback = _CLEANUPS.pop()
        try:
            callback()
        except Exception as exc:
            say("POLICY", f"cleanup failed: {exc}")
            failures.append(str(exc))
    return failures


def refuse(message: str, *, state: Optional[str] = None) -> "SystemExit":
    _run_cleanups()
    if state is not None:
        say("STATE", state)
    say("REFUSE", message)
    say("RESULT", "refused")
    raise SystemExit(2)


def finish_ok() -> int:
    say("RESULT", "ok")
    return 0


def run_git(*args: str, cwd: Path) -> "tuple[int, str, str]":
    proc = subprocess.run(
        ("git", *args), cwd=str(cwd), capture_output=True, text=True, check=False
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_must(*args: str, cwd: Path, what: str) -> str:
    code, out, err = run_git(*args, cwd=cwd)
    if code != 0:
        refuse(f"{what} failed: git {' '.join(args)} exited {code}. Got: {err!r:.200}")
    return out


def trash(path: Path) -> None:
    proc = subprocess.run(
        ("trash", str(path)), capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"trash failed: exit {proc.returncode}. Got: {proc.stderr!r:.100}"
        )


def is_ancestor(candidate: str, container: str, cwd: Path) -> bool:
    code, _, err = run_git("merge-base", "--is-ancestor", candidate, container, cwd=cwd)
    if code == 0:
        return True
    if code == 1:
        return False
    refuse(
        f"ancestry probe failed: merge-base --is-ancestor {candidate} {container} "
        f"exited {code}. Got: {err!r:.200}"
    )
    raise AssertionError("unreachable")


@dataclass
class Worktree:
    path: Path
    head: str
    branch: Optional[str]
    locked: bool
    lock_reason: Optional[str]


@dataclass
class Topology:
    common_dir: Path
    primary: Worktree
    worktrees: "list[Worktree]"

    @property
    def store(self) -> Path:
        return self.common_dir / "skill-worktree"

    @property
    def leases(self) -> Path:
        return self.store / "leases"

    @property
    def validations(self) -> Path:
        return self.store / "validations"


def parse_worktrees(anchor: Path) -> "list[Worktree]":
    out = git_must(
        "worktree", "list", "--porcelain", cwd=anchor, what="worktree listing"
    )
    entries: "list[Worktree]" = []
    path: Optional[Path] = None
    head = ""
    branch: Optional[str] = None
    locked = False
    lock_reason: Optional[str] = None

    def flush() -> None:
        nonlocal path, head, branch, locked, lock_reason
        if path is not None:
            entries.append(Worktree(path, head, branch, locked, lock_reason))
        path, head, branch, locked, lock_reason = None, "", None, False, None

    for line in out.splitlines():
        if line.startswith("worktree "):
            flush()
            path = Path(line[len("worktree ") :]).resolve()
        elif line.startswith("HEAD "):
            head = line[len("HEAD ") :]
        elif line.startswith("branch "):
            branch = line[len("branch ") :].removeprefix("refs/heads/")
        elif line == "detached":
            branch = None
        elif line == "locked":
            locked = True
        elif line.startswith("locked "):
            locked = True
            lock_reason = line[len("locked ") :]
    flush()
    if not entries:
        refuse(f"worktree parsing failed: no entries. Got: {out!r:.200}")
    return entries


def discover(anchor: Path) -> Topology:
    if not anchor.is_dir():
        refuse(f"anchor is not a directory. Got: {str(anchor)!r:.200}")
    code, out, err = run_git("rev-parse", "--git-common-dir", cwd=anchor)
    if code != 0:
        refuse(f"anchor is not inside a git worktree. Got: {err!r:.200}")
    common = Path(out)
    if not common.is_absolute():
        toplevel = git_must(
            "rev-parse", "--show-toplevel", cwd=anchor, what="toplevel probe"
        )
        common = (Path(toplevel) / common).resolve()
    common = common.resolve()
    worktrees = parse_worktrees(anchor)
    primary = worktrees[0]
    if primary.path != common.parent.resolve():
        refuse(
            "primary cross-check failed: first worktree entry "
            f"{str(primary.path)!r} != common-dir parent {str(common.parent)!r}"
        )
    topo = Topology(common, primary, worktrees)
    for component in (topo.store, topo.leases, topo.validations):
        if component.is_symlink():
            refuse(
                f"store integrity failed: {component} is a symlink; every "
                "skill-worktree store component must be a real directory under "
                "the git common dir — lease and record state must never "
                "resolve outside it"
            )
    if not topo.leases.is_dir() or not topo.validations.is_dir():
        refuse(
            "this repository has no skill-worktree store "
            f"(expected {topo.leases} and {topo.validations}); "
            "not a persistent-satellite repo — nothing for this skill to do here"
        )
    return topo


def find_worktree(topo: Topology, target: Path) -> Optional[Worktree]:
    resolved = target.resolve()
    for wt in topo.worktrees:
        if wt.path == resolved:
            return wt
    return None


def require_satellite(
    topo: Topology, sat_path: Path, worktree_arg: Optional[str]
) -> "tuple[Worktree, str]":
    wt = find_worktree(topo, sat_path)
    if wt is None:
        refuse(
            f"target is not a registered worktree of this repo. Got: {str(sat_path)!r:.200}"
        )
    assert wt is not None
    if wt.path == topo.primary.path:
        refuse(
            "target is the primary checkout, not a satellite; mutating verbs never touch the primary tree"
        )
    if not wt.locked:
        refuse(f"worktree {wt.path.name!r} is not locked; not a persistent satellite")
    if wt.lock_reason != CANONICAL_LOCK_REASON:
        refuse(
            f"worktree {wt.path.name!r} is locked with a non-canonical reason "
            f"{wt.lock_reason!r}; refusing to treat it as a satellite — adjudicate with the user"
        )
    identity = wt.path.name
    if worktree_arg is not None and worktree_arg != identity:
        refuse(
            f"identity mismatch: --worktree {worktree_arg!r} != directory basename {identity!r}"
        )
    return wt, identity


def session_identity() -> "tuple[str, str]":
    found = [(os.environ.get(var), runtime) for var, runtime in ENV_IDENTITIES]
    present = [(sid.strip(), runtime) for sid, runtime in found if sid and sid.strip()]
    if len(present) == 1:
        return present[0]
    if len(present) == 0:
        refuse(
            "no session identity: neither CLAUDE_CODE_SESSION_ID nor CODEX_THREAD_ID is set; "
            "lease-holding verbs require exactly one (inspect runs without identity)"
        )
    refuse(
        "ambiguous session identity: both CLAUDE_CODE_SESSION_ID and CODEX_THREAD_ID are set "
        "(nested runtimes?); unset the outer runtime's variable explicitly, e.g. "
        "`env -u CLAUDE_CODE_SESSION_ID ...`, so exactly one remains"
    )
    raise AssertionError("unreachable")


def maybe_identity() -> "Optional[tuple[str, str]]":
    found = [(os.environ.get(var), runtime) for var, runtime in ENV_IDENTITIES]
    present = [(sid.strip(), runtime) for sid, runtime in found if sid and sid.strip()]
    return present[0] if len(present) == 1 else None


def head_state(sat: Path) -> "tuple[Optional[str], str]":
    code, out, _ = run_git("symbolic-ref", "-q", "--short", "HEAD", cwd=sat)
    branch = out if code == 0 else None
    sha = git_must("rev-parse", "HEAD", cwd=sat, what="HEAD probe")
    return branch, sha


def op_markers(sat: Path) -> "list[str]":
    gitdir = Path(git_must("rev-parse", "--git-dir", cwd=sat, what="git-dir probe"))
    if not gitdir.is_absolute():
        gitdir = (sat / gitdir).resolve()
    return [marker for marker in OP_MARKERS if (gitdir / marker).exists()]


@dataclass
class TreeState:
    porcelain: "list[str]"
    reported_ignored: "list[str]"
    unknown_ignored: "list[str]"

    @property
    def clean(self) -> bool:
        return not self.porcelain and not self.unknown_ignored

    @property
    def ignored_state(self) -> str:
        if not self.reported_ignored:
            return "none present"
        return "report-and-record: " + ", ".join(sorted(self.reported_ignored)[:20])


@dataclass(frozen=True)
class InspectResult:
    """One helper-owned lifecycle classification and any hard-stop reason."""

    state: str
    refusal: Optional[str] = None


def classify_tree(sat: Path) -> TreeState:
    status = git_must("status", "--porcelain", cwd=sat, what="status probe")
    porcelain = [line for line in status.splitlines() if line]
    raw = git_must(
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
        "-z",
        cwd=sat,
        what="ignored-state probe",
    )
    reported: "list[str]" = []
    unknown: "list[str]" = []
    for path in (p for p in raw.split("\0") if p):
        base = os.path.basename(path)
        segments = path.split("/")
        if base in SILENT_IGNORED_BASENAMES:
            continue
        if (
            path.endswith(".pyc")
            or any(seg in REPORT_IGNORED_SEGMENTS for seg in segments)
            or any(path.startswith(prefix) for prefix in REPORT_IGNORED_PREFIXES)
        ):
            reported.append(path)
        else:
            unknown.append(path)
    return TreeState(porcelain, reported, unknown)


def require_clean(sat: Path, label: str) -> TreeState:
    tree = classify_tree(sat)
    if tree.unknown_ignored:
        refuse(
            f"unknown ignored path(s) in {label} tree: "
            + ", ".join(tree.unknown_ignored[:10])
            + " — hard stop per ignored-state policy"
        )
    if tree.porcelain:
        refuse(f"{label} tree is not clean: " + "; ".join(tree.porcelain[:10]))
    if tree.reported_ignored:
        policy(f"{label} ignored residue (report-and-record): {tree.ignored_state}")
    else:
        policy(f"{label} ignored residue: none present")
    return tree


def prove_parked(sat: Path, base: str, *, label: str = "satellite") -> TreeState:
    branch, sha = head_state(sat)
    if branch is not None:
        refuse(
            f"PARKED proof failed: {label} HEAD is on branch {branch!r}, not detached"
        )
    proof(f"detached HEAD at {sha}")
    tree = require_clean(sat, label)
    proof("clean per ignored-state policy")
    if not is_ancestor("HEAD", base, cwd=sat):
        refuse(
            f"PARKED proof failed: HEAD {sha} is not an ancestor of {base!r} "
            f"(PARKED-ORPHAN territory — surface `git log {base}..HEAD` to the user)"
        )
    proof(f"HEAD is ancestor of {base}")
    ahead = git_must(
        "rev-list", "--count", f"{base}..HEAD", cwd=sat, what="ahead count"
    )
    if ahead != "0":
        refuse(f"PARKED proof failed: {ahead} commit(s) in {base}..HEAD, expected 0")
    proof(f"rev-list --count {base}..HEAD = 0")
    return tree


def pin_base(topo: Topology, base: str) -> None:
    if topo.primary.branch is None:
        refuse("primary checkout is detached; cannot pin --base to its branch")
    if topo.primary.branch != base:
        refuse(
            f"--base {base!r} does not match the primary checkout's branch "
            f"{topo.primary.branch!r}; the base is never guessed — supply the branch "
            "the primary actually has checked out"
        )
    fact(f"base pinned: primary checkout is on {base!r}")


def lease_dir_for(topo: Topology, identity: str) -> Path:
    return topo.leases / f"wt-{identity}.lease"


INTEGRATION_LEASE = "integration.lease"


def read_owner(lease: Path) -> "tuple[str, Optional[dict]]":
    if not lease.exists():
        return "absent", None
    owner_file = lease / "owner.json"
    try:
        data = json.loads(owner_file.read_text())
    except (OSError, json.JSONDecodeError):
        return "unreadable", None
    if (
        not isinstance(data, dict)
        or not data.get("session_id")
        or not data.get("runtime")
    ):
        return "unreadable", None
    return "ok", data


def owner_summary(owner: "Optional[dict]") -> str:
    if owner is None:
        return "owner unreadable or absent"
    return (
        f"session_id={owner.get('session_id')!r} runtime={owner.get('runtime')!r} "
        f"worktree={owner.get('worktree')!r} branch={owner.get('branch')!r} "
        f"purpose={owner.get('purpose')!r} acquired_at={owner.get('acquired_at')!r}"
    )


def owner_payload(
    session: str,
    runtime: str,
    purpose: str,
    worktree: str,
    branch: Optional[str],
) -> dict:
    pid = os.getpid()
    ps = subprocess.run(
        ("ps", "-p", str(pid), "-o", "lstart="),
        capture_output=True,
        text=True,
        check=False,
    )
    pid_start = ps.stdout.strip() if ps.returncode == 0 else "unavailable"
    return {
        "session_id": session,
        "runtime": runtime,
        "acquired_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": purpose,
        "worktree": worktree,
        "branch": branch,
        "diag": {"pid": pid, "pid_start": pid_start, "host": socket.gethostname()},
    }


def validate_fleet_identity(identity: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identity):
        refuse(
            "fleet identity must be one safe path segment containing only letters, "
            f"digits, dot, underscore, or hyphen. Got: {identity!r:.100}"
        )


def absolute_without_final_resolution(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def path_kind(path: Path) -> str:
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return "absent"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def fleet_fingerprint(topo: Topology, identity: str, expected_path: Path) -> dict:
    matches = [wt for wt in topo.worktrees[1:] if wt.path.name == identity]
    return {
        "path_kind": path_kind(expected_path),
        "registered_paths": [str(wt.path) for wt in matches],
        "lock": [
            {
                "path": str(wt.path),
                "locked": wt.locked,
                "reason": wt.lock_reason,
                "head": wt.head or None,
            }
            for wt in matches
        ],
    }


def classify_owner(owner: dict, session: str, runtime: str) -> str:
    if owner.get("session_id") == session and owner.get("runtime") == runtime:
        return "SELF"
    return "FOREIGN"


def scope_matches(
    owner: dict, *, worktree: str, branch: Optional[str], purpose: Optional[str]
) -> bool:
    if owner.get("worktree") != worktree or owner.get("branch") != branch:
        return False
    return purpose is None or owner.get("purpose") == purpose


def acquire_lease(
    topo: Topology,
    lease: Path,
    payload: dict,
    session: str,
    runtime: str,
    *,
    purpose_in_scope: bool,
) -> str:
    if not lease.exists():
        staging = topo.leases / f".staging-{uuid.uuid4()}"
        staging.mkdir()
        (staging / "owner.json").write_text(json.dumps(payload, indent=2) + "\n")
        try:
            # rename refuses a non-empty target, and the staging protocol never
            # creates an empty lease dir, so mutual exclusion holds
            os.rename(staging, lease)
            return "acquired"
        except OSError:
            trash(staging)
    status, owner = read_owner(lease)
    if status != "ok" or owner is None:
        refuse(
            f"lease {lease.name} exists but its ownership is {status}; fail closed — "
            "an explicit user-authorized break (`trash` the lease dir) is required before re-lease"
        )
        raise AssertionError("unreachable")
    if classify_owner(owner, session, runtime) == "FOREIGN":
        refuse(
            f"lease {lease.name} is held by a FOREIGN session: {owner_summary(owner)}; "
            "fail closed — only an explicit user-authorized break may remove it"
        )
    if scope_matches(
        owner,
        worktree=payload["worktree"],
        branch=payload["branch"],
        purpose=payload["purpose"] if purpose_in_scope else None,
    ):
        policy(
            f"lease {lease.name} already held by this session with matching scope; re-entering"
        )
        return "reentered"
    refuse(
        f"lease {lease.name} is held by this session but with a DIFFERENT scope: "
        f"{owner_summary(owner)}; stale or ambiguous — adjudicate before re-leasing"
    )
    raise AssertionError("unreachable")


def require_self_wt_lease(
    topo: Topology, identity: str, branch: str, session: str, runtime: str
) -> dict:
    lease = lease_dir_for(topo, identity)
    status, owner = read_owner(lease)
    if status == "absent":
        refuse(
            f"no worktree lease held for {identity!r}; acquire it first (lease-acquire)"
        )
    if status == "unreadable" or owner is None:
        refuse(f"worktree lease for {identity!r} has unreadable ownership; fail closed")
        raise AssertionError("unreachable")
    if classify_owner(owner, session, runtime) != "SELF":
        refuse(
            f"worktree lease for {identity!r} is FOREIGN: {owner_summary(owner)}; fail closed"
        )
    if isinstance(owner.get("purpose"), str) and owner["purpose"].startswith("fleet:"):
        refuse(
            f"worktree lease for {identity!r} is fleet-purposed; task verbs never consume or release it"
        )
    if owner.get("worktree") != identity or owner.get("branch") != branch:
        refuse(
            f"worktree lease scope mismatch: lease says worktree={owner.get('worktree')!r} "
            f"branch={owner.get('branch')!r}, request is worktree={identity!r} branch={branch!r}"
        )
    proof(f"SELF worktree lease held for {identity!r} with matching scope")
    return owner


def record_file(topo: Topology, branch: str) -> Path:
    return topo.validations / (branch.replace("/", "--") + ".json")


def load_record(path: Path) -> "tuple[str, Optional[dict]]":
    # lstat-based check first: a symlink at a record path — live or dangling —
    # is never followed and never classified absent; records are regular files
    if path.is_symlink():
        return "symlink", None
    if not path.exists():
        return "absent", None
    if not path.is_file():
        # a FIFO, socket, or directory at a record path must classify
        # unreadable instead of blocking or erroring at open
        return "unreadable", None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "unreadable", None
    required = ("branch", "validated_tip", "ladder", "ignored_state", "timestamp")
    if not isinstance(data, dict):
        return "unreadable", None
    if any(not isinstance(data.get(key), str) or not data[key] for key in required):
        return "unreadable", None
    if not re.fullmatch(r"[0-9a-f]{40}", data["validated_tip"]):
        return "unreadable", None
    return "ok", data


def write_record(path: Path, payload: str) -> None:
    # a hardlinked record shares its inode with another name, so the O_TRUNC
    # write would mutate bytes reachable outside the store; O_NOFOLLOW cannot
    # see this — check the link count before opening
    if path.exists() and not path.is_symlink():
        if not path.is_file():
            refuse(
                f"record path {path.name} is not a regular file; fail closed — "
                "adjudicate with the user"
            )
        if path.stat().st_nlink > 1:
            refuse(
                f"record path {path.name} has {path.stat().st_nlink} filesystem "
                "links; a hardlinked record aliases bytes outside the validation "
                "store — fail closed; adjudicate with the user"
            )
    # O_NOFOLLOW makes the no-symlink rule an enforcement at the write itself,
    # not only a pre-check: a link at the final component fails open() instead
    # of being followed
    try:
        fd = os.open(
            str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644
        )
    except OSError as exc:
        refuse(
            f"record write refused: open {path.name} failed: {exc}; "
            "nothing was written through the record path"
        )
        raise AssertionError("unreachable")
    with os.fdopen(fd, "w") as fh:
        fh.write(payload)


def primary_op_markers(topo: Topology) -> "list[str]":
    return [marker for marker in OP_MARKERS if (topo.common_dir / marker).exists()]


def upstream_read(topo: Topology, base: str) -> None:
    code, out, _ = run_git(
        "rev-list",
        "--left-right",
        "--count",
        f"{base}...origin/{base}",
        cwd=topo.primary.path,
    )
    if code != 0:
        policy(
            f"no usable tracking ref for {base!r}; upstream check is a reported proof limitation, not a stop"
        )
        return
    parts = out.split()
    if len(parts) != 2:
        refuse(f"upstream probe parse failed. Got: {out!r:.100}")
    ahead, behind = int(parts[0]), int(parts[1])
    if behind > 0:
        refuse(
            f"{base!r} is behind origin/{base} by {behind} commit(s)"
            + (f" and ahead by {ahead}" if ahead else "")
            + "; landing onto a stale or diverged base is refused"
        )
    fact(
        f"upstream read: ahead {ahead}, behind 0 (ahead-only is the allowed steady state)"
    )


# ---------------------------------------------------------------- verbs


def _inspect(args: argparse.Namespace, *, emit_state: bool = True) -> InspectResult:
    """Emit current facts and return the canonical helper lifecycle state."""

    def result(state: str, refusal: Optional[str] = None) -> InspectResult:
        if emit_state:
            say("STATE", state)
        return InspectResult(state, refusal)

    topo = discover(Path(args.anchor))
    base: str = args.base
    pin_base(topo, base)
    ident = maybe_identity()
    if ident is None:
        policy(
            "no unambiguous session identity in env; lease facts reported as diagnostics only"
        )

    target = find_worktree(topo, Path(args.anchor))
    if target is None:
        refuse(f"anchor is not a registered worktree. Got: {args.anchor!r:.200}")
        raise AssertionError("unreachable")

    if target.path == topo.primary.path:
        fact(f"anchor is the primary checkout at {target.path} on {target.branch!r}")
        for wt in topo.worktrees[1:]:
            fact(
                f"satellite {wt.path.name!r}: head={wt.head[:12]} "
                f"branch={wt.branch!r} locked={wt.locked} reason={wt.lock_reason!r}"
            )
        staging_residue = sorted(p.name for p in topo.leases.glob(".staging-*"))
        if staging_residue:
            fact(
                f"lease staging residue ({len(staging_residue)}): "
                + ", ".join(staging_residue[:5])
                + " — crashed acquisitions; user-authorized trash to clear"
            )
        for lease in sorted(topo.leases.iterdir()):
            if lease.name.startswith("."):
                continue
            status, owner = read_owner(lease)
            fact(f"lease {lease.name}: {status} — {owner_summary(owner)}")
        for record in sorted(topo.validations.glob("*.json")):
            status, data = load_record(record)
            if status != "ok" or data is None:
                fact(f"validation record {record.name}: {status}")
                continue
            code, _, _ = run_git(
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{data['branch']}",
                cwd=topo.primary.path,
            )
            if code != 0:
                fact(
                    f"ORPHAN validation record {record.name}: branch {data['branch']!r} no longer "
                    "exists (cleanup via delete-branch's guarded absent-branch path)"
                )
        return result("PRIMARY")

    sat = target.path
    identity = sat.name
    fact(
        f"satellite {identity!r} at {sat} locked={target.locked} reason={target.lock_reason!r}"
    )
    lock_class = (
        "absent"
        if not target.locked
        else "canonical"
        if target.lock_reason == CANONICAL_LOCK_REASON
        else "noncanonical"
    )
    fact(f"lock={lock_class}")
    if not target.locked or target.lock_reason != CANONICAL_LOCK_REASON:
        policy(
            "lock is missing or non-canonical; mutating verbs will refuse this worktree"
        )

    markers = op_markers(sat)
    branch, sha = head_state(sat)
    tree = classify_tree(sat)
    fact(f"head: {'detached' if branch is None else 'branch ' + repr(branch)} at {sha}")
    fact(f"op markers: {markers or 'none'}")
    fact(
        f"tree: {'clean' if tree.clean else 'dirty'} "
        f"(porcelain {len(tree.porcelain)}, unknown-ignored {len(tree.unknown_ignored)}, "
        f"reported-ignored {len(tree.reported_ignored)})"
    )
    for path in tree.unknown_ignored[:10]:
        fact(f"unknown-ignored: {path}")
    contained = is_ancestor("HEAD", base, cwd=sat)
    ahead = int(
        git_must("rev-list", "--count", f"{base}..HEAD", cwd=sat, what="ahead count")
    )
    fact(
        f"ancestry: HEAD {'is' if contained else 'is NOT'} ancestor of {base!r}; ahead {ahead}"
    )

    lease = lease_dir_for(topo, identity)
    lease_status, owner = read_owner(lease)
    lease_class = "absent"
    lease_token = "absent"
    lease_purpose = "none"
    if lease_status != "absent":
        purpose_value = owner.get("purpose") if owner is not None else None
        lease_purpose = (
            "fleet"
            if isinstance(purpose_value, str) and purpose_value.startswith("fleet:")
            else "task"
            if isinstance(purpose_value, str) and purpose_value
            else "unknown"
        )
        if ident is not None and owner is not None:
            lease_class = classify_owner(owner, ident[0], ident[1])
            if lease_class == "SELF" and branch is not None:
                if not scope_matches(
                    owner, worktree=identity, branch=branch, purpose=None
                ):
                    lease_class = "SELF-SCOPE-MISMATCH"
        else:
            lease_class = f"present ({lease_status})"
        if lease_status != "ok" or owner is None:
            lease_token = "unreadable"
        elif ident is None or classify_owner(owner, ident[0], ident[1]) == "FOREIGN":
            lease_token = "foreign"
        elif (
            owner.get("worktree") != identity
            or (branch is not None and owner.get("branch") != branch)
            or (lease_purpose == "fleet" and owner.get("branch") is not None)
        ):
            lease_token = "scope-mismatch"
        else:
            lease_token = "self"
        fact(f"lease wt-{identity}.lease: {lease_class} — {owner_summary(owner)}")
    else:
        fact(f"lease wt-{identity}.lease: absent")
    fact(f"lease={lease_token}")
    fact(f"lease-purpose={lease_purpose}")

    rec_status: str = "absent"
    rec: Optional[dict] = None
    if branch is not None:
        rec_status, rec = load_record(record_file(topo, branch))
        rec_ok = (
            rec_status == "ok"
            and rec is not None
            and rec.get("branch") == branch
            and rec.get("validated_tip") == sha
        )
        fact(
            f"validation record for {branch!r}: {rec_status}"
            + (f", tip-match={rec_ok}" if rec_status == "ok" else "")
        )

    if markers:
        return result("ACTIVE-CONFLICT")
    if branch is None:
        if not tree.clean:
            return result(
                "UNMAPPABLE",
                "detached with a dirty tree maps to no lifecycle state; hard stop — "
                "surface the facts above to the user",
            )
        if not contained:
            inspection = result("PARKED-ORPHAN")
            policy(
                f"surface `git log {base}..HEAD` to the user; adopt / rescue ref / explicit discard are user calls"
            )
            return inspection
        if lease_status != "absent" and lease_class != "SELF":
            inspection = result("LEASE-ORPHANED")
            policy(
                "lease present but not verified SELF (foreign, unreadable, or owner "
                "unknown without session identity); surface the owner facts — only the "
                "user may authorize the break"
            )
            return inspection
        for record in sorted(topo.validations.glob("*.json")):
            status, data = load_record(record)
            if status != "ok" or data is None:
                continue
            code, _, _ = run_git(
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{data['branch']}",
                cwd=topo.primary.path,
            )
            if code == 0 and is_ancestor(data["branch"], base, cwd=topo.primary.path):
                inspection = result("PARKED-UNDELETED")
                fact(f"merged task branch still exists: {data['branch']!r}")
                return inspection
        return result("PARKED")

    if not tree.clean:
        inspection = result("IN-FLIGHT")
        policy(
            "uncommitted work present; never route a dirty tree to park or delete — adjudicate with the user"
        )
        return inspection
    if lease_status != "absent" and lease_class not in ("SELF", "SELF-SCOPE-MISMATCH"):
        # ahead of the containment split: every route out of an active branch
        # needs the worktree lease, so a lease this session cannot verify as its
        # own is the dominant fact — owner adjudication comes first
        inspection = result("LEASE-ORPHANED")
        policy(
            "lease present but not verified SELF (foreign, unreadable, or owner "
            "unknown without session identity); surface the owner facts — only the "
            "user may authorize the break"
        )
        return inspection
    if contained:
        rec_proves = (
            rec_status == "ok"
            and rec is not None
            and rec.get("branch") == branch
            and rec.get("validated_tip") == sha
            and is_ancestor(str(rec.get("validated_tip")), base, cwd=sat)
        )
        if rec_proves:
            return result("LANDED-UNPARKED")
        else:
            inspection = result("CONTAINED-UNPARKED")
            policy(
                "provenance unproven: the branch is contained in the base but no matching "
                "validation record proves a landing — it may be freshly activated or landed "
                "with its record gone; both are loss-free to park + `-d`, but state the "
                "ambiguity to the user before parking"
            )
            return inspection
    rec_valid = (
        rec_status == "ok"
        and rec is not None
        and rec.get("branch") == branch
        and rec.get("validated_tip") == sha
    )
    if not rec_valid:
        return result("READY-INVALID")
    if lease_class == "SELF":
        return result("READY")
    inspection = result("COMMITTED-UNLANDED")
    fact(f"lease state at interruption: {lease_class}")
    return inspection


def cmd_inspect(args: argparse.Namespace) -> int:
    inspection = _inspect(args)
    if inspection.refusal is not None:
        refuse(inspection.refusal)
    return finish_ok()


def cmd_lease_acquire(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    _, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    payload = owner_payload(session, runtime, args.purpose, identity, args.branch)
    outcome = acquire_lease(
        topo,
        lease_dir_for(topo, identity),
        payload,
        session,
        runtime,
        purpose_in_scope=True,
    )
    fact(f"worktree lease for {identity!r}: {outcome} (branch {args.branch!r})")
    return finish_ok()


def cmd_fleet_lease_acquire(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.anchor))
    anchor = find_worktree(topo, Path(args.anchor))
    if anchor is None or anchor.path != topo.primary.path:
        refuse("fleet lease verbs must be anchored at the primary checkout")
    identity = args.identity
    validate_fleet_identity(identity)
    purpose = args.purpose
    if not purpose.startswith("fleet:") or purpose == "fleet:":
        refuse(
            f"fleet lease purpose must start with 'fleet:' and name an operation. Got: {purpose!r:.100}"
        )
    expected_path = absolute_without_final_resolution(Path(args.path))
    lease = lease_dir_for(topo, identity)
    existing_status, existing_owner = read_owner(lease)
    if (
        existing_status == "ok"
        and existing_owner is not None
        and classify_owner(existing_owner, session, runtime) == "SELF"
        and scope_matches(
            existing_owner,
            worktree=identity,
            branch=None,
            purpose=purpose,
        )
        and existing_owner.get("expected_path") != str(expected_path)
    ):
        refuse(
            "fleet lease is held by this session but with a DIFFERENT scope: "
            f"expected-path {existing_owner.get('expected_path')!r} != {str(expected_path)!r}"
        )
    payload = owner_payload(session, runtime, purpose, identity, None)
    payload["expected_path"] = str(expected_path)
    payload["fingerprint"] = fleet_fingerprint(topo, identity, expected_path)
    outcome = acquire_lease(
        topo,
        lease,
        payload,
        session,
        runtime,
        purpose_in_scope=True,
    )
    fact(
        f"fleet lease for {identity!r}: {outcome} "
        f"(purpose {purpose!r}, expected path {str(expected_path)!r})"
    )
    return finish_ok()


def cmd_fleet_lease_release(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.anchor))
    anchor = find_worktree(topo, Path(args.anchor))
    if anchor is None or anchor.path != topo.primary.path:
        refuse("fleet lease verbs must be anchored at the primary checkout")
    identity = args.identity
    validate_fleet_identity(identity)
    expected_path = absolute_without_final_resolution(Path(args.path))
    lease = lease_dir_for(topo, identity)
    status, owner = read_owner(lease)
    if status == "absent":
        refuse(f"no fleet lease exists for {identity!r}; nothing to release")
    if status != "ok" or owner is None:
        refuse(
            f"fleet lease for {identity!r} has unreadable ownership; fail closed — "
            "user-authorized break only"
        )
    if classify_owner(owner, session, runtime) != "SELF":
        refuse(
            f"fleet lease for {identity!r} is FOREIGN: {owner_summary(owner)}; fail closed"
        )
    purpose = owner.get("purpose")
    if not isinstance(purpose, str) or not purpose.startswith("fleet:"):
        refuse(f"lease for {identity!r} is not fleet-purposed: {owner_summary(owner)}")
    if owner.get("worktree") != identity or owner.get("branch") is not None:
        refuse(f"fleet lease scope mismatch for {identity!r}: {owner_summary(owner)}")
    if owner.get("expected_path") != str(expected_path):
        refuse(
            f"fleet lease expected-path mismatch: owner has {owner.get('expected_path')!r}, "
            f"request has {str(expected_path)!r}"
        )
    original = owner.get("fingerprint")
    if not isinstance(original, dict):
        refuse(f"fleet lease for {identity!r} has no readable acquisition fingerprint")

    current = fleet_fingerprint(topo, identity, expected_path)
    registered = [wt for wt in topo.worktrees[1:] if wt.path.name == identity]
    kind = current["path_kind"]
    terminal: Optional[str] = None
    if not registered and kind == "absent":
        started_bare = (
            original.get("path_kind") == "absent"
            and original.get("registered_paths") == []
        )
        terminal = "bare" if started_bare else "decommissioned"
    elif len(registered) == 1 and kind == "directory":
        wt = registered[0]
        if (
            wt.path == expected_path.resolve()
            and wt.locked
            and wt.lock_reason == CANONICAL_LOCK_REASON
        ):
            if topo.primary.branch is None:
                refuse(
                    "primary checkout is detached; cannot prove a healthy fleet terminal"
                )
            inspection = _inspect(
                argparse.Namespace(
                    anchor=str(expected_path),
                    base=topo.primary.branch,
                ),
                emit_state=False,
            )
            if inspection.state != "PARKED" or inspection.refusal is not None:
                refuse(
                    f"fleet lease release refused: helper state {inspection.state} is not "
                    "PARKED; lease retained for recovery",
                    state="FLEET-OP",
                )
            terminal = "healthy"
    if terminal is None:
        fact(
            f"fleet release live state for {identity!r}: path_kind={kind!r} "
            f"registered_paths={current['registered_paths']!r}"
        )
        refuse(
            "fleet lease release requires a stable healthy, decommissioned, or bare "
            "terminal; lease retained for recovery",
            state="FLEET-OP",
        )
    trash(lease)
    fact(f"fleet lease for {identity!r} released; terminal={terminal}")
    return finish_ok()


def cmd_lease_release(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    wt, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    pin_base(topo, args.base)
    lease = lease_dir_for(topo, identity)
    status, owner = read_owner(lease)
    if status == "absent":
        refuse(f"no worktree lease exists for {identity!r}; nothing to release")
    if status == "unreadable" or owner is None:
        refuse(
            f"worktree lease for {identity!r} has unreadable ownership; fail closed — user-authorized break only"
        )
        raise AssertionError("unreachable")
    if classify_owner(owner, session, runtime) != "SELF":
        refuse(
            f"worktree lease for {identity!r} is FOREIGN: {owner_summary(owner)}; fail closed"
        )
    if isinstance(owner.get("purpose"), str) and owner["purpose"].startswith("fleet:"):
        refuse(
            f"worktree lease for {identity!r} is fleet-purposed; task lease-release cannot release it"
        )
    branch, _ = head_state(wt.path)
    if branch is not None:
        refuse(
            f"satellite is on branch {branch!r}: releasing a lease mid-task is the early release "
            "the lifecycle forbids; park first (or the user explicitly authorizes abandonment)"
        )
    prove_parked(wt.path, args.base)
    trash(lease)
    fact(f"worktree lease for {identity!r} released (satellite proven PARKED)")
    return finish_ok()


def cmd_activate(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    wt, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    require_self_wt_lease(topo, identity, args.branch, session, runtime)
    pin_base(topo, args.base)
    if op_markers(wt.path):
        refuse(f"operation in progress in satellite: {op_markers(wt.path)}")
    prove_parked(wt.path, args.base)
    code, _, _ = run_git(
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/heads/{args.branch}",
        cwd=topo.primary.path,
    )
    if code == 0:
        refuse(
            f"task branch name {args.branch!r} already exists; task branches are repo-global and fresh"
        )
    proof(f"branch name {args.branch!r} is free")
    git_must(
        "switch", "-c", args.branch, args.base, cwd=wt.path, what="activation switch"
    )
    tip = git_must("rev-parse", "HEAD", cwd=wt.path, what="tip probe")
    base_sha = git_must(
        "rev-parse", args.base, cwd=topo.primary.path, what="base probe"
    )
    if tip != base_sha:
        refuse(f"activation base proof failed: tip {tip} != {args.base} {base_sha}")
    proof(
        f"activated {args.branch!r} from explicit {args.base!r} ref; tip == {base_sha}"
    )
    return finish_ok()


def cmd_record_validation(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    wt, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    branch, sha = head_state(wt.path)
    if branch is None:
        refuse("satellite is detached; validation records bind to a task branch")
        raise AssertionError("unreachable")
    require_self_wt_lease(topo, identity, branch, session, runtime)
    if op_markers(wt.path):
        refuse(f"operation in progress in satellite: {op_markers(wt.path)}")
    tree = require_clean(wt.path, "satellite")
    path = record_file(topo, branch)
    status, previous = load_record(path)
    if status == "ok" and previous is not None:
        if previous["branch"] != branch:
            refuse(
                f"record filename collision: {path.name} already holds a record for "
                f"branch {previous['branch']!r}, not {branch!r}; fail closed"
            )
        policy(f"superseding prior record (validated_tip {previous['validated_tip']})")
    elif status == "symlink":
        refuse(
            f"record path {path.name} is a symlink; records are regular files "
            "inside the validation store and are never written through a link — "
            "the symlink and its target are preserved as evidence; adjudicate "
            "with the user"
        )
    elif status != "absent":
        refuse(
            f"existing record file {path.name} is {status}; fail closed — its bytes "
            "are preserved as evidence; adjudicate with the user before touching it"
        )
    record = {
        "branch": branch,
        "validated_tip": sha,
        "ladder": args.ladder,
        "ignored_state": tree.ignored_state,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_record(path, json.dumps(record, separators=(",", ":")) + "\n")
    proof(f"validation record bound: {branch!r} @ {sha}")
    return finish_ok()


def cmd_land(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    wt, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    require_self_wt_lease(topo, identity, args.branch, session, runtime)

    payload = owner_payload(session, runtime, "integration", identity, args.branch)
    integration = topo.leases / INTEGRATION_LEASE
    acquire_lease(topo, integration, payload, session, runtime, purpose_in_scope=True)
    proof("integration lease held")

    def _release_integration() -> None:
        status, owner = read_owner(integration)
        if (
            status == "ok"
            and owner is not None
            and classify_owner(owner, session, runtime) == "SELF"
        ):
            try:
                trash(integration)
            except Exception as exc:
                raise RuntimeError(
                    f"integration lease release failed: {exc}; "
                    f"lease remains at {integration}"
                ) from exc
            fact("integration lease released")

    _CLEANUPS.append(_release_integration)
    try:
        # re-read the primary's branch live: the lease span exists to re-verify
        # this fact, so the discover()-time snapshot must not be trusted here
        live_base = git_must(
            "symbolic-ref",
            "--short",
            "HEAD",
            cwd=topo.primary.path,
            what="live primary branch probe",
        )
        if live_base != args.base:
            refuse(
                f"--base {args.base!r} does not match the primary checkout's live "
                f"branch {live_base!r} (re-read under the integration lease)"
            )
        proof(f"primary is on {args.base!r} (re-read live under the integration lease)")
        primary_status = git_must(
            "status", "--porcelain", cwd=topo.primary.path, what="primary status"
        )
        if primary_status:
            refuse(
                "primary tree is not clean: "
                + "; ".join(primary_status.splitlines()[:10])
            )
        proof("primary clean (status --porcelain empty)")
        markers = primary_op_markers(topo)
        if markers:
            refuse(f"operation in progress in primary: {markers}")
        proof("no operation markers in primary")
        upstream_read(topo, args.base)
        if not is_ancestor(args.base, args.branch, cwd=topo.primary.path):
            refuse(
                f"freshness failed: {args.base!r} is not an ancestor of {args.branch!r} — "
                "rebase in the satellite, revalidate (new validated_tip), re-enter",
                state="STALE-BASE",
            )
        proof(f"freshness: {args.base!r} is ancestor of {args.branch!r}")
        rec_status, rec = load_record(record_file(topo, args.branch))
        if rec_status != "ok" or rec is None:
            refuse(
                f"validation record for {args.branch!r} is {rec_status}; READY-INVALID — "
                "barred from integration until revalidated"
            )
            raise AssertionError("unreachable")
        if rec["branch"] != args.branch:
            refuse(
                f"record cross-check failed: embedded branch {rec['branch']!r} != {args.branch!r} "
                "(filename collision fails closed)"
            )
        tip = git_must(
            "rev-parse",
            f"refs/heads/{args.branch}",
            cwd=topo.primary.path,
            what="tip probe",
        )
        if tip != rec["validated_tip"]:
            refuse(
                f"validation binding failed: branch tip {tip} != validated_tip "
                f"{rec['validated_tip']}; revalidate before landing"
            )
        proof(f"branch tip == validated_tip ({tip})")
        require_clean(wt.path, "satellite")
        proof("satellite clean")
        branch_now, _ = head_state(wt.path)
        fact(f"satellite currently on: {branch_now!r}")
        code, out, err = run_git(
            "merge", "--ff-only", rec["validated_tip"], cwd=topo.primary.path
        )
        if code != 0:
            refuse(f"ff-only merge failed (nothing changed): {err or out!r:.200}")
        if not is_ancestor(rec["validated_tip"], args.base, cwd=topo.primary.path):
            refuse(
                f"landed proof FAILED after merge reported success: {rec['validated_tip']} not in "
                f"{args.base!r} — evidence contradiction, stop and surface"
            )
        proof(f"landed: {rec['validated_tip']} is ancestor of {args.base!r}")
    finally:
        cleanup_failures = _run_cleanups()
    if cleanup_failures or integration.exists():
        refuse(
            "landing completed (see PROOF lines) but the integration lease was NOT "
            "released: "
            + ("; ".join(cleanup_failures) or "lease dir still present")
            + f" — {integration} remains; re-running this land from this session "
            "re-enters and releases it, or a user-authorized `trash` of it is "
            "required from any other session"
        )
    return finish_ok()


def cmd_park(args: argparse.Namespace) -> int:
    session, runtime = session_identity()
    topo = discover(Path(args.sat_path))
    wt, identity = require_satellite(topo, Path(args.sat_path), args.worktree)
    branch, sha = head_state(wt.path)
    lease_branch = branch if branch is not None else args.branch
    if lease_branch is None:
        refuse(
            "satellite already detached and no --branch given; supply --branch to match the held lease scope"
        )
        raise AssertionError("unreachable")
    require_self_wt_lease(topo, identity, lease_branch, session, runtime)
    pin_base(topo, args.base)
    if op_markers(wt.path):
        refuse(f"operation in progress in satellite: {op_markers(wt.path)}")
    require_clean(wt.path, "satellite")
    if branch is None:
        code, _, _ = run_git(
            "rev-parse",
            "--verify",
            "--quiet",
            f"refs/heads/{lease_branch}",
            cwd=topo.primary.path,
        )
        if code == 0 and not is_ancestor(
            lease_branch, args.base, cwd=topo.primary.path
        ):
            refuse(
                f"leased task branch {lease_branch!r} has commits not contained in "
                f"{args.base!r} — unlanded work; landing or explicit user-authorized "
                "abandonment must come first (a detached satellite does not hide it)"
            )
    if not is_ancestor("HEAD", args.base, cwd=wt.path):
        refuse(
            f"containment proof failed: HEAD {sha} is not an ancestor of {args.base!r} — "
            "unlanded work; landing or explicit user-authorized abandonment must come first"
        )
    proof(f"containment: HEAD is ancestor of {args.base!r}")
    if branch is not None:
        git_must("switch", "--detach", args.base, cwd=wt.path, what="park detach")
    else:
        policy("already detached; skipping switch and completing the re-park proofs")
    prove_parked(wt.path, args.base)
    trash(lease_dir_for(topo, identity))
    fact(f"worktree lease for {identity!r} released (proven re-park)")
    return finish_ok()


def cmd_delete_branch(args: argparse.Namespace) -> int:
    topo = discover(Path(args.sat_path))
    require_satellite(topo, Path(args.sat_path), args.worktree)
    pin_base(topo, args.base)
    for wt in topo.worktrees:
        if wt.branch == args.branch:
            refuse(
                f"branch {args.branch!r} is checked out in worktree {wt.path}; park it first"
            )
    proof(f"{args.branch!r} is not checked out in any worktree")
    rec_path = record_file(topo, args.branch)
    rec_status, rec = load_record(rec_path)
    code, _, _ = run_git(
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/heads/{args.branch}",
        cwd=topo.primary.path,
    )
    if code != 0:
        fact(f"branch {args.branch!r} does not exist")
        if rec_status == "absent":
            refuse(
                f"branch and validation record both absent for {args.branch!r}; nothing to do — "
                "probably already completed"
            )
        if rec_status != "ok" or rec is None:
            refuse(
                f"orphan record for {args.branch!r} is {rec_status}; adjudicate with the user"
            )
            raise AssertionError("unreachable")
        if rec["branch"] != args.branch:
            refuse(
                f"orphan record cross-check failed: embedded branch {rec['branch']!r} != "
                f"{args.branch!r}; adjudicate with the user"
            )
        if not is_ancestor(rec["validated_tip"], args.base, cwd=topo.primary.path):
            refuse(
                f"orphan record's validated_tip {rec['validated_tip']} is NOT contained in "
                f"{args.base!r}; possible unlanded loss — surface for user adjudication, never trash"
            )
        proof(
            f"orphan record's validated_tip is contained in {args.base!r} — prior completion"
        )
        trash(rec_path)
        fact(f"orphan validation record for {args.branch!r} trashed")
        return finish_ok()
    if rec_status == "symlink":
        refuse(
            f"record path {rec_path.name} is a symlink; adjudicate with the user "
            "before deletion — the branch and the link are left untouched"
        )
    if not is_ancestor(args.branch, args.base, cwd=topo.primary.path):
        refuse(
            f"{args.branch!r} is not contained in {args.base!r}: unlanded work — deletion "
            "would need `-D`, which is a user-authorized abandonment, never this verb"
        )
    proof(f"{args.branch!r} is ancestor of {args.base!r}")
    code, out, err = run_git("branch", "-d", args.branch, cwd=topo.primary.path)
    if code != 0:
        refuse(
            f"`git branch -d` refused despite ancestry proof and pre-verifications: "
            f"{err or out!r:.200} — evidence contradiction, stop (never -D)"
        )
    proof(f"branch {args.branch!r} safe-deleted")
    if rec_status == "absent":
        policy("validation record already absent (already trashed)")
    elif rec_status == "ok" and rec is not None and rec["branch"] == args.branch:
        trash(rec_path)
        fact(f"validation record for {args.branch!r} trashed")
    else:
        policy(
            f"record file {rec_path.name} kept: "
            + (
                rec_status
                if rec_status != "ok" or rec is None
                else f"it belongs to branch {rec['branch']!r}, not {args.branch!r} (filename collision)"
            )
            + " — adjudicate with the user before touching it"
        )
    return finish_ok()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="worktree_cycle.py",
        description="Guarded lifecycle verbs for persistent-satellite worktrees.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)

    def add(
        name: str, func, *, anchor_help: str, with_base: bool = True
    ) -> argparse.ArgumentParser:
        p = sub.add_parser(name)
        p.set_defaults(func=func)
        p.add_argument("sat_path" if name != "inspect" else "anchor", help=anchor_help)
        if with_base:
            p.add_argument(
                "--base",
                required=True,
                help="integration branch; must equal the primary checkout's branch",
            )
        p.add_argument(
            "--worktree",
            help="optional satellite identity cross-check (directory basename)",
        )
        return p

    add("inspect", cmd_inspect, anchor_help="primary or satellite path (pure read)")
    p = add(
        "lease-acquire",
        cmd_lease_acquire,
        anchor_help="satellite path",
        with_base=False,
    )
    p.add_argument("--branch", required=True)
    p.add_argument("--purpose", required=True)
    p = sub.add_parser("fleet-lease-acquire")
    p.set_defaults(func=cmd_fleet_lease_acquire)
    p.add_argument("anchor", help="primary checkout path")
    p.add_argument("--identity", required=True)
    p.add_argument("--path", required=True, help="expected satellite path")
    p.add_argument("--purpose", required=True)
    p = sub.add_parser("fleet-lease-release")
    p.set_defaults(func=cmd_fleet_lease_release)
    p.add_argument("anchor", help="primary checkout path")
    p.add_argument("--identity", required=True)
    p.add_argument("--path", required=True, help="expected satellite path")
    add("lease-release", cmd_lease_release, anchor_help="satellite path")
    p = add("activate", cmd_activate, anchor_help="satellite path")
    p.add_argument("--branch", required=True)
    p = add(
        "record-validation",
        cmd_record_validation,
        anchor_help="satellite path",
        with_base=False,
    )
    p.add_argument("--ladder", required=True)
    p = add("land", cmd_land, anchor_help="satellite path")
    p.add_argument("--branch", required=True)
    p = add("park", cmd_park, anchor_help="satellite path")
    p.add_argument(
        "--branch", help="lease-scope branch when the satellite is already detached"
    )
    p = add(
        "delete-branch",
        cmd_delete_branch,
        anchor_help="satellite path (anchor for discovery)",
    )
    p.add_argument("--branch", required=True)
    return parser


def main(argv: "list[str]") -> int:
    if sys.version_info < MIN_PYTHON:
        say(
            "REFUSE",
            f"requires Python >= {'.'.join(map(str, MIN_PYTHON))}; running {sys.version.split()[0]}",
        )
        say("RESULT", "refused")
        return 2
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

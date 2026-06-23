#!/usr/bin/env bash
# release-cut-facts.sh — read-only FACT reporter for the release-cut skill.
#
# It computes the deterministic facts a release cut needs and REPORTS them. It
# decides nothing and writes nothing: the agent reads these facts, makes the one
# judgment that matters — the change-class / next-version call — and edits the
# manifest and CHANGELOG itself. This mirrors the report-and-delegate shape of
# check-library-integrity.sh: the script reports, the agent decides.
#
# Reports, for ONE release unit:
#   1. manifest       first present of plugin.json / package.json /
#                     pyproject.toml / Cargo.toml (presence-ordered) + its version
#   2. changelog      CHANGELOG.md presence and its top dated-heading version/date
#   3. lockstep       whether the manifest version and the top CHANGELOG heading
#                     agree (AGREE = already cut at that version: do not double-bump)
#   4. touched units  given a commit range, which top-level units it changed
#                     (multi-unit guard: cut each unit separately)
#   5. marketplace    this-repo only (skipped elsewhere): whether each
#                     plugins/marketplace.json source.path still resolves
#
# The authoritative version is the MANIFEST, never a git tag. Read-only: no
# writes, no network. Exit 0 after reporting (drift is a fact, not a failure);
# exit 2 only on a usage error or when no manifest is found.
#
# Usage: release-cut-facts.sh <release-unit-dir> [<commit-range>]
#   <release-unit-dir>  directory holding the manifest, e.g. plugins/git-cycle or .
#   <commit-range>      optional, e.g. main..HEAD — to report touched units
set -euo pipefail

unit="${1:-}"
range="${2:-}"

case "$unit" in
  -h|--help) echo "usage: $0 <release-unit-dir> [<commit-range>]"; exit 0 ;;
  "") echo "usage: $0 <release-unit-dir> [<commit-range>]" >&2; exit 2 ;;
esac
[ -d "$unit" ] || { echo "release-cut-facts: not a directory: $unit" >&2; exit 2; }
unit="${unit%/}"

kv() { printf '  %-16s %s\n' "$1" "$2"; }

# --- 1: authoritative manifest (presence-ordered) + current version ---------
manifest="" mkind="" version=""
for cand in ".claude-plugin/plugin.json:plugin.json" \
            "package.json:package.json" \
            "pyproject.toml:pyproject.toml" \
            "Cargo.toml:Cargo.toml"; do
  rel="${cand%%:*}" kind="${cand##*:}"
  if [ -f "$unit/$rel" ]; then manifest="$unit/$rel" mkind="$kind"; break; fi
done

if [ -z "$manifest" ]; then
  echo "release-cut-facts: no manifest found in $unit" >&2
  echo "  searched: .claude-plugin/plugin.json, package.json, pyproject.toml, Cargo.toml" >&2
  echo "  (the manifest is authoritative — never derive a version from a git tag)" >&2
  exit 2
fi

case "$mkind" in
  plugin.json|package.json)
    version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("version",""))' "$manifest" 2>/dev/null || true)"
    ;;
  pyproject.toml|Cargo.toml)
    # First `version = "x"` line (best effort; the agent confirms against the file).
    version="$(grep -E '^[[:space:]]*version[[:space:]]*=' "$manifest" | head -1 \
                 | sed -E 's/^[^=]*=[[:space:]]*"?([^"#]+)"?.*/\1/' | tr -d '[:space:]' || true)"
    ;;
esac

echo "== release unit: $unit =="
kv "manifest" "$manifest ($mkind)"
kv "version" "${version:-<none found — set one before cutting>}"

# --- 2 + 3: CHANGELOG state and manifest<->changelog lockstep ----------------
changelog="$unit/CHANGELOG.md"
cl_version="" cl_date=""
if [ -f "$changelog" ]; then
  heading="$(grep -m1 -E '^##[[:space:]]+[^#]' "$changelog" || true)"
  cl_version="$(printf '%s' "$heading" | sed -E 's/^##[[:space:]]+([^[:space:]]+).*/\1/')"
  cl_date="$(printf '%s' "$heading" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1 || true)"
  kv "changelog" "$changelog (top: ${cl_version:-?}${cl_date:+ — $cl_date})"
else
  kv "changelog" "ABSENT (create it in lockstep, or record a deliberate no-changelog decision)"
fi

if [ ! -f "$changelog" ]; then
  kv "lockstep" "n/a — no CHANGELOG"
elif [ -n "$version" ] && [ "$version" = "$cl_version" ]; then
  kv "lockstep" "AGREE ($version) — already cut at this version; do NOT double-bump"
else
  kv "lockstep" "DIFFER manifest=${version:-?} changelog-top=${cl_version:-?} — reconcile at the cut"
fi

# --- 4: touched units in a commit range (multi-unit guard) -------------------
if [ -n "$range" ]; then
  if files="$(git diff --name-only "$range" 2>/dev/null)"; then
    units="$(printf '%s\n' "$files" \
               | awk -F/ 'NF>=2 && ($1=="plugins"||$1=="skills"||$1=="skills-claude"){print $1"/"$2}' \
               | sort -u)"
    nplugins="$(printf '%s\n' "$units" | grep -c '^plugins/' || true)"
    if [ -z "$units" ]; then
      kv "touched units" "$range changed no plugins/ or skills/ unit"
    else
      kv "touched units" "$range touched:"
      printf '%s\n' "$units" | sed 's/^/                     /'
      [ "${nplugins:-0}" -gt 1 ] && \
        kv "MULTI-UNIT" "more than one plugin changed — cut each release unit separately"
    fi
  else
    kv "touched units" "could not diff range '$range' (not a valid range here)"
  fi
fi

# --- 5: marketplace source.path resolution (this-repo only; read-only) -------
root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
mp="${root:+$root/plugins/marketplace.json}"
if [ -n "$mp" ] && [ -f "$mp" ]; then
  out="$(python3 - "$mp" <<'PY' 2>/dev/null || true
import json, os, sys
mp = json.load(open(sys.argv[1]))
home = os.path.expanduser("~")
bad = []
for p in mp.get("plugins", []):
    rel = p.get("source", {}).get("path", "")
    # Codex resolves the personal marketplace relative to $HOME.
    if not rel.startswith("./") or not os.path.isdir(os.path.join(home, rel[2:])):
        bad.append(p.get("name", "?") + " -> " + (rel or "<none>"))
print("OK" if not bad else "UNRESOLVED: " + "; ".join(bad))
PY
)"
  kv "marketplace" "${out:-<unchecked>}"
fi

echo "  (facts only — you make the change-class / next-version call and write the files)"

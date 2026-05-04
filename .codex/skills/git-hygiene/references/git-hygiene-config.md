# Git Hygiene Config

Use this reference when `.git-hygiene.json` exists at repo root or when the user wants to customize hygiene behavior.

## Example

```json
{
  "ignorePatterns": ["*.log", "tmp/", ".cache/"],
  "protectedPatterns": [".env*", "*.key", "secrets/"],
  "groupingHints": {
    "src/auth/": "auth",
    "src/api/": "api",
    "tests/": "test"
  },
  "branchProtection": ["main", "develop", "release/*"],
  "defaultCommitPrefix": "chore"
}
```

## Field semantics

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `ignorePatterns` | array of strings | Patterns that should usually become `.gitignore` additions. Treat them as candidates to preview, not silent changes. |
| `protectedPatterns` | array of strings | Extra patterns that must never be auto-deleted. Require explicit per-file confirmation. |
| `groupingHints` | object | Maps paths or path prefixes to concern labels that help semantic grouping. |
| `branchProtection` | array of strings | Branch names or globs that should never be proposed for deletion. |
| `defaultCommitPrefix` | string | Conventional Commits type to use when a group is real but its type is ambiguous. |

## Rules

- Load this file only from repo root.
- If the file is malformed JSON, report that and ignore it for the run.
- Treat all config-driven actions as previewable proposals, not silent mutations.
- Let repo protection rules extend built-in safety rules; never let them weaken protected-file handling.

## Notes

- `ignorePatterns` should usually drive `.gitignore` updates, not file deletion.
- `groupingHints` improve naming and grouping, but should not override clear evidence from the diff itself.
- `branchProtection` extends the default protections for current branch, default branch, and active worktree branches.

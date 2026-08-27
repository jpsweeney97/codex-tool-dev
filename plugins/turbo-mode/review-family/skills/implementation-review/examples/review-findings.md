# Implementation Review Examples

Load only when `SKILL.md` is not enough.

## Finding Shape

```markdown
### Findings
1. [blocker] Expired tokens remain valid at the boundary
   - Location: `auth.py:42`, `validate_token()`
   - Finding type: implementation
   - Spec expectation: Auth spec step 4 says tokens must be denied at expiry time.
   - Observed behavior: `now == expiry` is accepted.
   - Evidence: R3 expects denial; `auth.py:42` uses `if now <= expiry:`.
   - Consequence: Tokens have an authentication bypass window at expiry.
   - Fix: Use `now < expiry` and add a boundary test.

### Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|
| R3 | Reject expired tokens immediately | violated | Auth spec step 4 | `auth.py:42` accepts `now <= expiry` | Checked `now == expiry`; code accepts it |
```

Strong findings connect requirement, code, falsification, and consequence.

## Bounded Review Shape

An omitted requirement carries `unverified` status, not a `blocker` finding: omission is what bounded mode means, and `Partial review only` already withholds clearance for it.

```markdown
### Bounded Review Scope
Reviewed authentication requirements R1-R4 only. Billing callbacks (plan steps 8-10) were not inspected.

### Findings
No findings (in the reviewed slice)

### Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|
| R8 | Billing callbacks are idempotent | unverified | Billing plan steps 8-10 | not inspected — outside the reviewed subset | none this pass |

### Verdict
- Blocker count: 0
- Verdict: Partial review only
- Next slice: billing callbacks (`billing/callbacks.py`)
```

A genuine in-slice `blocker` is the opposite case — precedence renders `Blocked`, scoped to the slice, never hidden behind the incomplete-pass label:

```markdown
### Bounded Review Scope
Reviewed authentication requirements R1-R4 only. Billing callbacks (plan steps 8-10) were not inspected.

### Findings
1. [blocker] Expired tokens remain valid at the boundary (fields as in Finding Shape above)

### Verdict
- Blocker count: 1
- Verdict: Blocked — scoped to the reviewed slice; billing callbacks remain `unverified`
```

## Split Required Shape

```markdown
### Bounded Review Scope
Reviewed the auth changes only; the diff bundles four independent concerns across 1,400 changed lines.

### Findings
No findings (in the reviewed slice)

### Verdict
- Blocker count: 0 (in the reviewed slice)
- Verdict: Split required
- Split seams:
  1. Token-validation behavior change (`auth.py`, `tests/test_auth.py`) — the actual risk surface; review first.
  2. Logging-format refactor (`logging/*.py`) — pure rename, no behavior change; separate so it does not hide the auth change.
  3. DB migration adding `sessions.last_seen` (`migrations/0042.sql`) — lock/backfill physics; review on its own.
  4. Dependency bump `requests 2.28→2.31` (`requirements.txt`) — changelog/CVE check, unrelated to the rest.
```

Each seam is single-purpose and clears on its own; bundled, the auth regression hides in the refactor noise.

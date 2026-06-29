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

```markdown
### Bounded Review Scope
Reviewed authentication requirements R1-R4 only.

### Findings
1. [blocker] Billing callback requirements remain unverified
   - Location: `billing/callbacks.py`
   - Finding type: unverified
   - Spec expectation: Billing plan steps 8-10 require idempotent callbacks.
   - Observed behavior: This pass did not inspect billing callbacks.
   - Evidence: Scope omitted `billing/callbacks.py`.
   - Consequence: No ship verdict is justified for the full implementation.
   - Fix: Review billing callbacks next.

### Verdict
- Blocker count: 1
- Verdict: Partial review only
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

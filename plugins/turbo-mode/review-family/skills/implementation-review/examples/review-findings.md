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

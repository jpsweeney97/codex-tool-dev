# Implementation Review Examples

Use these examples to keep the review adversarial, evidence-based, and specific.

## Strong Finding

```markdown
### 2. Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|
| R3 | Reject expired tokens immediately | violated | Auth spec step 4: "Deny tokens at expiry time." | `auth.py:42` uses `if now <= expiry:` | Checked boundary condition at `now == expiry`; code still accepts the token |

### 3. Findings
1. [blocker] Expired tokens remain valid at the boundary
   - Location: `auth.py:42`, `validate_token()`
   - Spec expectation: Tokens must be denied at expiry time.
   - Observed behavior: The implementation accepts tokens when `now == expiry`.
   - Evidence: Spec step 4 requires immediate denial. The code uses `<=` instead of `<`.
   - Why it matters: This creates an authentication bypass window on every token expiry event.
   - Fix: Change the comparison to `if now < expiry:` and add a boundary test for `now == expiry`.
```

Why this is strong:

- Ties the finding to a specific requirement
- Shows the exact falsification attempt
- Separates expected behavior from observed behavior
- Gives a concrete failure consequence and fix

## Weak Finding

```markdown
- Severity: nitpick
- Location: `auth.py`
- Issue: Could maybe validate tokens more carefully
- Why it matters: Security best practice
- Fix: Consider adding more checks
```

Why this is weak:

- No requirement reference
- No code evidence
- No failure mechanism
- Wrong severity for an auth bypass
- Uses hedged language instead of a defensible claim

## Strong Spec-Deviation Finding

```markdown
### 2. Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|
| R5 | Validate idempotency key before creating an order | violated | Checkout plan step 7 | `api/handlers.py:87-94` creates the order before checking the key | Traced concurrent duplicate requests; both can create orders before the key check runs |

### 3. Findings
1. [should-fix] Idempotency check runs after order creation
   - Location: `api/handlers.py:87-94`, `create_order()`
   - Spec expectation: Validate the idempotency key before creating the order.
   - Observed behavior: The handler persists the order first and validates the key afterward.
   - Evidence: Checkout plan step 7 and the call order in `create_order()`.
   - Why it matters: Concurrent retries can create duplicate orders and duplicate charges.
   - Fix: Move the idempotency check ahead of `Order.create()` and use locking or an atomic uniqueness constraint.
```

## Strong Plan Finding

```markdown
### 3. Findings
2. [should-fix] Plan over-specifies JSON Schema validation for a free-form field
   - Location: Plan step 3, "validate input schema"
   - Spec expectation: Accept `metadata` as a free-form dictionary per the API contract.
   - Observed behavior: The plan requires strict JSON Schema validation with no exception for `metadata`.
   - Evidence: API contract section 2.4 allows arbitrary `metadata`; plan step 3 does not.
   - Why it matters: A faithful implementation of the plan would reject valid requests.
   - Fix: Update the plan to validate required fields while allowing `metadata` as passthrough data with size limits.
```

## Justified Zero-Findings Review

Zero findings are allowed only when the review still shows adversarial work.

```markdown
### 2. Requirements Ledger
| ID | Requirement | Status | Spec source | Code evidence | Falsification attempt |
|----|-------------|--------|-------------|---------------|-----------------------|
| R1 | Soft-delete accounts with 30-day recovery | satisfied | Account deletion spec step 2 | `models.py:18-29`, `handlers.py:90-121` set `deleted_at` and filter active users | Checked for hard-delete paths and found none in scope |
| R2 | Hide soft-deleted accounts from normal queries | satisfied | Account deletion spec step 3 | `querysets.py:11-24` filters on `deleted_at IS NULL` | Checked list, detail, and login paths for missing active-user filter |
| R3 | Allow recovery during the retention window | satisfied | Account deletion spec step 4 | `handlers.py:130-168` restores users when `deleted_at` is within 30 days | Tried boundary case at exactly 30 days and verified the comparison matches the spec |

### 4. Unverified Areas
- Background cleanup job — not part of the changed scope, so retention expiry behavior remains unreviewed here

### 5. Verdict
- Blocker count: 0
- Verdict: Ship
- Highest-risk area: Recovery boundary handling if time zone assumptions change
- Strongest failed attack attempt: Searched for any hard-delete path in the changed account deletion flow and did not find one
- Plan gaps surfaced during review: None in reviewed scope
```

Why this is acceptable:

- Every requirement is listed
- Each `satisfied` claim cites both the spec and the code
- Each changed area has a documented falsification attempt
- Residual uncertainty is still called out

## Fake Clean Review

```markdown
Implementation looks good overall. I did not notice any major problems. Ship it.
```

Why this is unacceptable:

- No ledger
- No adversarial pass
- No evidence
- No stated attack attempts
- Reassurance language replaces actual review work

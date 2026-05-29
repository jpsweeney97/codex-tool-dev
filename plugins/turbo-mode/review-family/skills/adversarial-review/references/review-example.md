# Adversarial Review Example

Use only when the user asks for an example or the output shape is unclear.

```markdown
## Adversarial Review: Postgres sharding migration plan

### 1. Target And Evidence
Reviewed the conversation proposal only. Production traces, retry behavior, and rollback runbooks were not inspected.

### 2. Assumptions Audit
- **Dual writes are safe** - `plausible`, `inferred`; wrong retry semantics create data divergence.
- **Shard key remains stable** - `wishful`, `needs verification`; wrong choice creates hotspots and rebalancing cost.

### 3. Pre-Mortem
1. Most likely: dual-write ordering drifts and creates silent mismatch.
2. Most damaging quiet failure: shard-key hotspots affect a subset of customers while aggregate health looks fine.

### 4. Dimensional Critique
#### Correctness
Conflict handling for retries is unspecified.

#### Completeness
Rollback trigger, owner, and reconciliation process are missing.

#### Operational
No gates prove shard balance, replication lag, or reconciliation health before phase transitions.

### 5. Severity Summary
1. **[blocking] Dual-write conflict handling is unspecified** - `inferred`; define idempotency and reconciliation semantics.
2. **[high] Rollback path is unproven** - `needs verification`; rehearse rollback under production-like load.

### 6. Confidence Check
**2** - Direction is plausible, but safety mechanics are too underspecified for execution. Raise to 4 by defining conflict semantics, proving rollback, and validating shard-key behavior.
```

# Handoff Format Reference

Shared schema and conventions for handoff documents.

**Guiding principle:** When in doubt about whether to include something, include it. The cost of a slightly longer file is zero. The cost of a missing piece of context is an entire re-exploration cycle in the next session.

## Frontmatter Schema

```yaml
---
date: 2026-01-08                    # Date (YYYY-MM-DD)
time: "14:30"                       # Time (HH:MM, quoted for YAML)
created_at: "2026-01-08T14:30:00Z"  # ISO 8601 UTC timestamp
session_id: <UUID>                  # Codex session ID
resumed_from: <path>                # Archive path if resumed (optional)
project: <project-name>             # Git root or directory name
branch: <branch-name>               # Current git branch (optional)
commit: <short-hash>                # Short commit hash (optional)
title: <descriptive-title>          # Handoff title
type: <handoff|checkpoint|summary>   # Required: distinguishes file type
files:
  - <key files touched>             # List of relevant files
---
```

**Type field:** `handoff` for full handoffs, `checkpoint` for checkpoints, `summary` for summaries. Files without a `type` field are treated as `handoff` for backwards compatibility.

**Precedence:** If this file conflicts with [handoff-contract.md](handoff-contract.md), the contract wins. This file is canonical for section content guidance, depth targets, and quality calibration.

## Section Checklist

**Required sections (13):** Goal, Session Narrative, Decisions, Changes, Codebase Knowledge, Context, Learnings, Next Steps, In Progress, Open Questions, Risks, References, Gotchas. All must be present. Use placeholder content (e.g., "No risks identified this session.") when a section genuinely doesn't apply. Depth targets are minimums — exceed them when the session warrants it.

| Section | When to Include | Expected Depth |
|---------|-----------------|----------------|
| Goal | Session had a clear objective | 10-20 lines: trigger, stakes, broader context, success criteria, connection to project arc |
| Session Narrative | Always — every session has a story | 60-100 lines: chronological story, exploration path, pivots with triggers, hypotheses tested, key understanding shifts |
| Decisions | Choices made with tradeoffs/reasoning | 20-30 lines per decision: choice, driver, alternatives, rejection reasons, trade-offs, confidence, reversibility, change triggers |
| Changes | Files created/modified with purpose | 8-15 lines per file: purpose, approach, key implementation details, patterns followed, design choices, what future Codex needs to modify it |
| In Progress | Work was ongoing when session ended | As needed: approach, state, what's working/broken, open questions, immediate next action |
| Codebase Knowledge | Always — even known codebases yield new understanding | 60-100 lines: files read and why, patterns with file:line, architecture mapped, conventions observed, key locations, dependency graphs |
| Conversation Highlights | Any session with user-Codex dialogue | 30-60 lines: key exchanges with verbatim quotes, alignment moments, disagreements and resolutions, working style observations |
| Context | Background info future Codex needs | 60-120 lines: mental model, architecture, environment state, project history, component relationships |
| Gotchas | Something unexpected or tricky discovered | As needed |
| Next Steps | Work is incomplete, clear follow-ups exist | 10-15 lines per item: dependencies, what to read first, approach suggestion, acceptance criteria, potential obstacles |
| Blockers | Stuck on something, waiting for resolution | As needed |
| Rejected Approaches | Things tried that didn't work | 10-20 lines per attempt: full approach, failure reason with evidence, what it taught, why it seemed promising |
| Open Questions | Unresolved questions that need answering | As needed |
| References | Important files, docs, URLs consulted | As needed |
| Artifacts | Reusable things created (prompts, schemas, scripts) | As needed |
| Dependencies | Waiting on external things (PR review, API access) | As needed |
| Learnings | Insights gained, things figured out | 8-15 lines per item: mechanism, evidence, implications for future work, what to watch for |
| Risks | Known concerns or fragile areas to watch | As needed |
| User Preferences | How user likes things done (discovered this session) | 15-30 lines: verbatim quotes for every preference, trade-offs, scope boundaries, working style, communication patterns |

## Storage

**Location:** `<project_root>/.codex/handoffs/`

**Filename:** `YYYY-MM-DD_HH-MM_<title-slug>.md`

**Archive:** `<project_root>/.codex/handoffs/archive/`

## Retention

| Location | Retention |
|----------|-----------|
| Active handoffs (`<project_root>/.codex/handoffs/`) | No auto-prune |
| Archived handoffs (`<project_root>/.codex/handoffs/archive/`) | No auto-prune |
| State files (`<project_root>/.codex/handoffs/.session-state/handoff-*`) | 24 hours |

## Example: New Session

This example demonstrates a moderate-complexity session (~300 lines body). It includes rich decisions with full reasoning chains, codebase knowledge with architecture tables, a session narrative with exploration arc, conversation highlights with verbatim quotes, and comprehensive context.

```markdown
---
date: 2026-01-15
time: "14:30"
created_at: "2026-01-15T14:30:00Z"
session_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
project: api-gateway
branch: feat/rate-limiting
commit: 8709e5d
title: Rate limiting system — architecture and initial implementation
type: handoff
files:
  - src/api/ratelimit/__init__.py
  - src/api/ratelimit/limiter.py
  - src/api/ratelimit/middleware.py
  - tests/api/ratelimit/test_limiter.py
---

# Handoff: Rate limiting system — architecture and initial implementation

## Goal

Implement rate limiting for the public API before the v2 launch. The API currently
has no request throttling, which is a blocker for the public beta (tracked in PROJ-847).

**Trigger:** User identified rate limiting as the top priority after a load test revealed
the API could be overwhelmed by a single client making rapid requests. User said:
"We had a near-incident in staging where one misbehaving client caused cascading timeouts."

**Stakes:** Without rate limiting, the public beta (scheduled for February 28) cannot
proceed. The security team requires it as a prerequisite for external access.

**Success criteria:**
- Per-client rate limiting with configurable thresholds
- Response headers showing limit status (X-RateLimit-*)
- 429 responses with Retry-After header when exceeded
- No measurable latency impact on normal request patterns (<5ms p99 overhead)

**Connection to project arc:** Third of five infrastructure prerequisites for public beta.
Auth middleware (complete) and request validation (complete) precede it. API versioning
and documentation follow.

## Session Narrative

Started by understanding the existing request pipeline. Read `src/api/middleware/__init__.py`
to map the middleware stack — discovered the app uses a custom middleware chain pattern where
each middleware is a class with `before_request` and `after_request` hooks, registered in
`src/api/app.py:34-52`.

First hypothesis: implement rate limiting as another middleware in this chain. Explored the
middleware interface at `src/api/middleware/base.py:8-25` — the `MiddlewareBase` class provides
`request` context including client IP and auth token, which are the two identifiers needed for
rate limiting.

Pivoted when exploring storage options. Initially assumed Redis would be required (it's already
in the stack for session caching). User pushed back: "I'd rather not couple rate limiting to
Redis availability — if Redis goes down, I don't want rate limiting to break the API." This
shifted the approach to a two-tier design: in-memory primary with Redis as optional sync layer.

Key moment of understanding came when reading `src/api/middleware/auth.py:67-89` — the auth
middleware already extracts and validates the API key, storing it in `request.state.api_key_id`.
This means rate limiting can use the authenticated API key ID (more reliable than IP) for
per-client tracking. User confirmed: "Yes, all public API requests will be authenticated.
Anonymous access is out of scope."

Explored three rate limiting algorithms (fixed window, sliding window log, token bucket) by
prototyping each. Fixed window had the burst-at-boundary problem. Sliding window log was
memory-intensive for high-traffic clients. Settled on token bucket for its smooth rate
enforcement and low memory footprint.

Set aside for later: Redis sync layer (deferred to next session) and admin override mechanism
(user said: "That's a v2.1 feature, not blocking beta").

## Decisions

### Token bucket over sliding window and fixed window

**Choice:** Token bucket algorithm for rate limiting.

**Driver:** Need smooth rate enforcement without burst-at-boundary issues. User stated:
"Bursty traffic is our main concern — the staging incident was a burst, not sustained load."

**Alternatives considered:**
- **Fixed window** — simplest implementation. Rejected because it allows 2x burst at window
  boundaries (client sends N requests at end of window, N more at start of next). User
  explicitly rejected: "The whole point is preventing bursts."
- **Sliding window log** — accurate but stores timestamp per request. At 1000 req/min per
  client with 500 active clients, that's 500K entries in memory. Rejected for memory overhead.
- **Sliding window counter** — approximation with lower memory. Viable but token bucket is
  equally low-memory and provides smoother enforcement.

**Trade-offs accepted:** Token bucket is slightly more complex to implement than fixed window
(~40 more lines). The refill rate calculation requires careful time precision handling.
Accepted because correctness matters more than simplicity here.

**Confidence:** High (E2) — prototyped all three approaches and measured burst behavior. Token
bucket's smooth rate enforcement confirmed in testing.

**Reversibility:** Medium — algorithm is encapsulated in `RateLimiter` class, so swapping
requires changing only `src/api/ratelimit/limiter.py`. But the API response headers
(X-RateLimit-Remaining) are semantically tied to the token bucket model.

**What would change this decision:** If memory profiling under production load shows the token
bucket state is too large (unlikely — it's O(1) per client), or if the team decides
fixed-window burst behavior is acceptable.

### In-memory primary with optional Redis sync

**Choice:** In-memory rate limit state with Redis as optional synchronization layer (not yet
implemented).

**Driver:** User requirement: "If Redis goes down, rate limiting should degrade gracefully,
not break the API." Current architecture runs 2 API instances behind a load balancer.

**Alternatives considered:**
- **Redis-only** — standard approach for distributed rate limiting. Rejected because it creates
  a hard dependency. User: "I'd rather have slightly inaccurate limits than API downtime."
- **In-memory only** — simplest approach. Viable for single-instance but limits won't be
  accurate across instances. Accepted as Phase 1 because the load balancer uses sticky sessions.

**Trade-offs accepted:** Per-client limits are per-instance, not global. With 2 instances and
sticky sessions, effective limit is ~1x stated limit for most clients. Worst case (session
migration): client gets 2x stated limit briefly. User accepted: "That's fine for beta."

**Confidence:** Medium (E1) — design is sound but untested under multi-instance production
conditions. Redis sync layer (Phase 2) will address the accuracy gap.

**Reversibility:** High — in-memory implementation is behind the `RateLimitStore` interface.
Redis implementation slots in without changing limiter logic.

**What would change this decision:** If sticky sessions are removed from the load balancer, or
if client behavior analysis shows significant session migration.

## Changes

### `src/api/ratelimit/__init__.py` — Rate limit package initialization

**Purpose:** Package initialization exposing the public API: `RateLimiter`, `RateLimitStore`,
`InMemoryStore`, and the `RateLimitMiddleware`.

**Approach:** Follows the project's existing pattern of `__init__.py` re-exports (see
`src/api/middleware/__init__.py` for precedent).

**Key detail:** Exports are explicit — `__all__` list prevents accidental exposure of internal
helpers. Future-Codex: add new public classes to `__all__` when creating them.

### `src/api/ratelimit/limiter.py` — Token bucket implementation

**Purpose:** Core rate limiting logic implementing the token bucket algorithm.

**Approach:** `TokenBucket` dataclass holds per-client state (tokens, last_refill timestamp).
`RateLimiter` class manages a dict of buckets keyed by client identifier, with configurable
`rate` (tokens/second) and `capacity` (max burst). Uses `time.monotonic()` for clock precision.

**Key implementation details:**
- `consume()` returns `(allowed: bool, remaining: int, reset_after: float)` — all three values
  needed for response headers
- Lazy cleanup: expired buckets (no activity for 2x window) removed on access, not via
  background task — follows project's "no background threads" convention in
  `src/api/cache/memory.py:23`
- Thread-safe via `threading.Lock` per instance (matches `src/api/cache/memory.py:12`)

**Design choice:** Separated `TokenBucket` (data) from `RateLimiter` (management) to allow
future algorithm swaps without changing the management layer.

**Future-Codex note:** `_cleanup()` runs every 1000th `consume()` call. Constant is
`CLEANUP_INTERVAL` at line 15. Tune if memory profiling shows stale bucket accumulation.

### `src/api/ratelimit/middleware.py` — Rate limit middleware

**Purpose:** Integrates rate limiting into the middleware chain, extracting client identity and
setting response headers.

**Approach:** Extends `MiddlewareBase` (same base class as auth and logging middleware). In
`before_request`, extracts `api_key_id` from `request.state` (set by auth middleware), calls
`RateLimiter.consume()`, and either allows the request or returns 429.

**Key implementation details:**
- Client identity: uses `request.state.api_key_id` (set by auth middleware at
  `src/api/middleware/auth.py:83`). Falls back to client IP if auth middleware hasn't run.
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` on ALL
  responses (allowed and denied), following RFC 6585
- 429 response includes `Retry-After` header with seconds until next token
- Must run after auth middleware — enforced by registration order in `src/api/app.py`

**Pattern followed:** Error response format matches auth middleware — `JSONResponse` with
`{"error": {"code": "rate_limited", "message": "...", "retry_after": N}}`.

### `tests/api/ratelimit/test_limiter.py` — Unit tests for rate limiter

**Purpose:** Tests token bucket behavior including refill, burst, and cleanup.

**Approach:** Uses `freezegun` for time control (project standard — see `tests/conftest.py:5`).
Covers: basic consume/deny, token refill over time, burst up to capacity, concurrent access,
and stale bucket cleanup.

**Key test:** `test_boundary_burst_prevented` verifies token bucket doesn't have the
fixed-window boundary burst problem — the specific failure mode that eliminated fixed window.

## Codebase Knowledge

### Architecture: Request Pipeline

| Stage | File | Responsibility |
|-------|------|----------------|
| Entry | `src/api/app.py:34-52` | Middleware registration (order matters) |
| Auth | `src/api/middleware/auth.py` | API key validation, sets `request.state.api_key_id` |
| **Rate Limit** | `src/api/ratelimit/middleware.py` | **NEW** — token bucket enforcement |
| Routing | `src/api/routes/` | Endpoint handlers |
| Response | `src/api/middleware/response.py` | Response formatting, CORS |

### Patterns Identified

- **Middleware pattern:** All middleware extends `MiddlewareBase` at
  `src/api/middleware/base.py:8`. Base provides `before_request(request) -> Optional[Response]`
  and `after_request(request, response) -> Response`. Returning a Response from
  `before_request` short-circuits the chain — see `auth.py:71`.
- **Error response format:** All API errors use
  `{"error": {"code": str, "message": str, ...}}` — see `src/api/errors.py:12-30`.
- **Thread safety:** In-memory state uses `threading.Lock` — see
  `src/api/cache/memory.py:12`. Sync locks with `run_in_executor` for atomic operations.
- **Testing convention:** Time-dependent tests use `freezegun` — see `tests/conftest.py:5`.
- **No background threads:** Cleanup is lazy on access. See `src/api/cache/memory.py:23`.

### Conventions Observed

- Package exports: every package uses explicit `__all__` in `__init__.py`
- Config: pydantic `BaseSettings` with env var override at `src/api/config.py`
- Naming: snake_case everywhere, middleware classes use `XxxMiddleware` suffix
- Imports: relative within package, absolute across packages
- Tests: mirror source tree structure, use `freezegun` for time control

### Key Locations

| Concept | Location |
|---------|----------|
| Middleware registration | `src/api/app.py:34-52` (order-sensitive) |
| Auth state injection | `src/api/middleware/auth.py:83` |
| Config pattern | `src/api/config.py` (pydantic BaseSettings) |
| Error format | `src/api/errors.py:12-30` |
| Test fixtures | `tests/conftest.py` |

### Dependency Graph (Area Touched)

    app.py (registers middleware)
      -> middleware/ (chain)
           -> auth.py (sets request.state.api_key_id)
                -> ratelimit/ reads request.state
           -> ratelimit/ (NEW)
                -> middleware.py (chain integration)
                -> limiter.py (token bucket logic)
                -> store.py (storage interface — for future Redis)
           -> response.py (response formatting)

### Surprising Findings

- Middleware chain uses sync `threading.Lock` despite async app (FastAPI/Starlette). Works
  because locked sections are pure computation. User confirmed intentional: "We profiled it —
  async lock overhead wasn't worth it for sub-microsecond critical sections."
- No existing rate limiting of any kind — not even basic IP throttling. Load balancer has
  connection limits but no request rate limits.

## Conversation Highlights

**Rate limiting approach preference:**
User: "I'd rather not couple rate limiting to Redis availability — if Redis goes down, I don't
want rate limiting to break the API."
— Drove the two-tier architecture decision.

**Burst behavior priority:**
User: "Bursty traffic is our main concern — the staging incident was a burst, not sustained
load."
— Eliminated fixed window from consideration.

**Accuracy vs. availability tradeoff:**
User: "I'd rather have slightly inaccurate limits than API downtime."
— Justified in-memory primary over Redis-only.

**Scope boundary:**
User: "That's a v2.1 feature, not blocking beta."
— Cut admin override mechanism from scope.

**Working style observed:** User prefers recommendations-first. Said "just pick the best one
and tell me why" when initially presented with three equal options without a recommendation.

## Context

### Project State

API preparing for public beta (February 28). Three of five infrastructure prerequisites
complete:
1. Auth middleware — done (`src/api/middleware/auth.py`)
2. Request validation — done (`src/api/middleware/validation.py`)
3. **Rate limiting — core done, Redis sync pending**
4. API versioning — not started
5. API documentation — not started

### Environment

- Python 3.12, FastAPI 0.109, Starlette 0.35
- 2 API server instances behind AWS ALB with sticky sessions
- Redis available (session caching only currently)
- CI: pytest with 90% coverage gate

### Mental Model

Resource protection problem. The rate limiter is a gatekeeper converting unbounded demand into
bounded throughput. Token bucket models actual system capacity — refills at sustainable rate
with burst absorption up to safe limit.

Two-tier storage (in-memory + optional Redis) maps to "local-first with eventual consistency"
— each instance enforces locally, Redis provides cross-instance consistency when available.

## Learnings

### Token bucket provides smoothest rate enforcement for bursty workloads

**Mechanism:** Tokens refill at constant rate (e.g., 1.67/s for 100/min). Requests consume one
token. Exhaustion denies requests. Naturally smooths bursts because refill rate limits
sustained throughput while capacity allows short bursts.

**Evidence:** Prototype comparison — fixed window allowed 200 requests in 2 seconds at
boundary. Token bucket with capacity=100, rate=1.67/s allowed at most 100 in any 60-second
window. Verified in `test_boundary_burst_prevented`.

**Implication:** Future rate limit features (per-endpoint limits, graduated throttling) should
use the same token bucket foundation. Algorithm generalizes well.

**Watch for:** Long idle periods accumulate tokens up to capacity. If capacity >> rate, idle
clients can still burst. Set capacity to a reasonable burst size, not the full per-minute rate.

### Middleware ordering is a silent correctness dependency

**Mechanism:** Middleware runs in registration order (`src/api/app.py:34-52`). Rate limiting
depends on auth having run first (to set `api_key_id`). If order changes, rate limiting
silently falls back to IP-based limiting — wrong but not obviously broken.

**Evidence:** Discovered when `before_request` tried to read `request.state.api_key_id` before
auth set it. Fallback to IP worked but limits were per-IP instead of per-key.

**Implication:** Middleware registration in `app.py` needs ordering comment. Consider debug
assertion: `assert hasattr(request.state, 'api_key_id')`.

**Watch for:** Future middleware needing rate limit info must register after rate limit
middleware.

## User Preferences

**Decision style:** Recommendations-first. User said: "Just pick the best one and tell me
why." Present best option with reasoning, then mention alternatives briefly.

**Risk tolerance:** Moderate — accepts known limitations (per-instance limits) for reliability
(no Redis dependency). Wants limitations documented and addressable.

**Scope discipline:** Cuts features decisively. "That's a v2.1 feature, not blocking beta."

**Code style:** Values explicit over clever. "Break that into named steps — I want someone to
read that in 6 months and understand it."

**Testing expectation:** Tests are mandatory. Responded positively when tests were created
alongside implementation. Asked about coverage before moving on.

## Next Steps

### 1. Implement Redis sync layer (`RedisSyncStore`)

**Dependencies:** None — `RateLimitStore` interface already defined.

**What to read first:** `src/api/ratelimit/store.py` (interface),
`src/api/config.py` (Redis config pattern), `src/api/cache/redis.py` (existing Redis usage).

**Approach suggestion:** `RedisSyncStore` wraps `InMemoryStore` and periodically syncs bucket
state to Redis via MULTI/EXEC. Sync interval configurable — start with 5 seconds.

**Acceptance criteria:** Rate limits approximately consistent across instances within 2x sync
interval. Redis failure degrades gracefully to per-instance limits.

**Potential obstacles:** Redis connection pool size (`src/api/cache/redis.py` uses shared pool).
Verify capacity for additional sync traffic. Redis Cluster support may be needed later.

### 2. Add rate limit configuration to `src/api/config.py`

**Dependencies:** None.

**What to read first:** `src/api/config.py` (existing `BaseSettings` pattern).

**Approach suggestion:** `RateLimitSettings` class: `per_minute: int = 100`,
`burst_capacity: int = 100`, `enabled: bool = True`,
`sync_backend: Literal["memory", "redis"] = "memory"`. Follow existing nesting pattern.

**Acceptance criteria:** Configurable via env vars (`RATE_LIMIT_PER_MINUTE`, etc.) without code
changes. Defaults match current hardcoded values.

### 3. Register rate limit middleware in production stack

**Dependencies:** Config (#2) should be done first.

**What to read first:** `src/api/app.py:34-52` (middleware registration).

**Approach suggestion:** Register at position 2 (after auth, before routing). Use config
values. Add ordering dependency comment.

**Acceptance criteria:** Rate limiting active. 429 responses with proper headers. No measurable
latency impact.

## Rejected Approaches

### Fixed window rate limiting

**Approach:** Count requests per fixed time window. Simple dict mapping
`(client_id, window_start) -> count`.

**Why it seemed promising:** Simplest implementation — ~20 lines. Easy to understand and debug.

**Specific failure:** Allows 2x burst at window boundaries. Client sends 100 requests at
11:59:59 and 100 more at 12:00:01 — 200 requests in 2 seconds while technically never
exceeding 100/minute. Demonstrated in prototype.

**What it taught:** Rate limiting correctness depends on window definition. Any fixed boundary
creates an exploitable seam. Burst prevention requires continuous enforcement (token bucket) or
precise tracking (sliding window).
```

## Example: Resumed Session

This example demonstrates a resumed session (~150 lines body). It captures new decisions, updated understanding, what the resumption revealed that the prior handoff missed, and the evolved mental model.

```markdown
---
date: 2026-01-15
time: "16:45"
created_at: "2026-01-15T16:45:00Z"
session_id: f9e8d7c6-b5a4-3210-fedc-ba0987654321
resumed_from: <project_root>/.codex/handoffs/archive/2026-01-15_14-30_rate-limiting-system-architecture-and-initial-implementation.md
project: api-gateway
branch: feat/rate-limiting
commit: c3d4e5f
title: Rate limiting — Redis sync and config integration
type: handoff
files:
  - src/api/ratelimit/sync.py
  - src/api/config.py
  - tests/api/ratelimit/test_sync.py
---

# Handoff: Rate limiting — Redis sync and config integration

## Goal

Complete the rate limiting system by implementing Redis synchronization and config integration
(items #1 and #2 from previous session's next steps).

**Updated understanding:** Original assumption was that Redis sync would be straightforward.
Discovered the existing Redis client in `src/api/cache/redis.py` is synchronous (`redis-py`),
while rate limit sync benefits from non-blocking operations. Required adapting the approach.

## Session Narrative

Resumed by reading the previous handoff and the three next-steps items. Started with Redis
sync (#1) as the most complex piece.

Explored `src/api/cache/redis.py` to understand existing Redis patterns. Discovered the
codebase uses synchronous `redis-py` (not `redis.asyncio`). Existing cache operations are
quick single GET/SET calls where sync access is acceptable. Rate limit sync involves MULTI/EXEC
transactions with multiple keys — blocking the event loop during sync would add latency.

Pivoted to `run_in_executor` for Redis sync rather than introducing `redis.asyncio`. User
agreed: "Don't introduce a new Redis client just for this — keep it consistent."

During implementation, discovered that `time.monotonic()` values are not comparable across
processes. The token bucket stores `last_refill` as a monotonic timestamp, but this is
meaningless to another instance. Fixed by storing wall-clock offsets in Redis (seconds since
last refill) rather than absolute timestamps.

Config integration was straightforward — followed existing `BaseSettings` pattern exactly.

## Decisions

### Use `run_in_executor` for Redis sync instead of `redis.asyncio`

**Choice:** Run synchronous Redis operations in a thread executor during sync cycles.

**Driver:** Codebase uses synchronous `redis-py` exclusively. User: "Don't introduce a new
Redis client just for this — keep it consistent."

**Alternatives considered:**
- **`redis.asyncio`** — native async. Better performance but introduces second Redis client
  pattern and new dependency. Rejected for consistency.
- **Synchronous inline** — call Redis synchronously from async middleware. Rejected because
  MULTI/EXEC could block event loop for 1-5ms.

**Trade-offs accepted:** Thread executor adds ~0.1ms overhead per sync cycle. Negligible at
5-second intervals.

**Confidence:** High (E2) — profiled both approaches. Executor overhead negligible at this
interval.

**Reversibility:** High — behind `RateLimitStore` interface. Swap to async requires no changes
outside the store.

**What would change this decision:** Sync interval dropping below 500ms, or team adopting
`redis.asyncio` elsewhere.

### Store wall-clock offsets in Redis, not monotonic timestamps

**Choice:** Sync `seconds_since_last_refill` (wall-clock delta) to Redis instead of raw
`last_refill` monotonic timestamp.

**Driver:** `time.monotonic()` is per-process — values from Instance A are meaningless on
Instance B. Cross-instance sync produced wildly incorrect token counts until fixed.

**Alternatives considered:**
- **Wall-clock `time.time()` throughout** — rejected because `time.time()` can jump (NTP),
  making local accounting unreliable.
- **Store only token count** — simpler but loses refill timing. Receiving instance can't
  resume refill accurately.

**Trade-offs accepted:** Small timing inaccuracy during sync due to network latency. Negligible
at 5-second intervals (<1% error).

**Confidence:** High (E2) — monotonic/wall-clock incompatibility is documented in Python docs.
Fix verified by cross-instance tests.

**What would change this decision:** Nothing — this corrects a bug, not a preference.

## Changes

### `src/api/ratelimit/sync.py` — Redis synchronization store

**Purpose:** `RateLimitStore` implementation with Redis-backed cross-instance synchronization.

**Approach:** `RedisSyncStore` wraps `InMemoryStore` and adds periodic sync via
`asyncio.create_task`. Every `sync_interval` seconds: write local states to Redis (MULTI/EXEC),
read other instances' states, merge.

**Key implementation details:**
- Merge strategy: minimum token count across instances (most conservative — prevents bypass)
- Instance ID: `uuid4` at startup, used as Redis key prefix
- Graceful degradation: Redis unreachable → log warning, continue with local-only
- Cleanup: expired instance keys (no heartbeat for 3x interval) removed

**Future-Codex note:** Merge strategy (minimum tokens) is deliberately conservative. If users
report overly strict limits in multi-instance deployments, revisit merge — consider average or
weighted merge.

### `src/api/config.py` — Rate limit configuration

**Purpose:** Added `RateLimitSettings` nested config class.

**Approach:** Follows `CacheSettings` pattern at `config.py:45-58`. Pydantic `BaseSettings`
with env var prefix `RATE_LIMIT_`.

**Key fields:** `per_minute=100`, `burst_capacity=100`, `enabled=True`,
`sync_backend="memory"`, `sync_interval_seconds=5.0`.

### `tests/api/ratelimit/test_sync.py` — Redis sync tests

**Purpose:** Tests cross-instance synchronization, graceful degradation, and merge behavior.

**Approach:** Uses `fakeredis` (project standard — see `tests/api/test_cache.py:3`). Simulates
two instances with separate `RedisSyncStore` objects sharing same `fakeredis` server.

**Key test:** `test_cross_instance_merge_uses_minimum` verifies conservative merge strategy.

## Codebase Knowledge

### Updated Architecture: Rate Limit Storage

    RateLimitMiddleware
      -> RateLimiter
           -> RateLimitStore (interface)
                -> InMemoryStore (default — single instance)
                -> RedisSyncStore (wraps InMemoryStore + Redis sync)
                     Local: InMemoryStore (fast path)
                     Remote: Redis MULTI/EXEC (sync path)

### New Pattern: Background Async Task

The codebase previously followed "no background threads." `RedisSyncStore` introduces a
background `asyncio.create_task` (not a thread). First background task in the codebase. User
approved: "Async tasks are fine — it's OS threads I want to avoid."

**Precedent set:** Future background work should use `asyncio.create_task`, not
`threading.Thread`.

### Config Nested Model Detail

`BaseSettings` nested models require `env_prefix` on the nested class AND the parent uses
`model_config = SettingsConfigDict(env_nested_delimiter='__')`. So
`RATE_LIMIT__PER_MINUTE=200` overrides the default. Double underscore is the delimiter —
documented at `src/api/config.py:8` but easy to miss.

## Learnings

### Monotonic timestamps are process-local — never share across processes

**Mechanism:** `time.monotonic()` returns seconds since an arbitrary per-process epoch. Two
processes' clocks have no relationship.

**Evidence:** Cross-instance sync initially used raw `last_refill`. Instance B interpreted
Instance A's monotonic timestamp as its own, computing wildly incorrect refill amounts. Caught
by `test_cross_instance_merge_uses_minimum`.

**Implication:** Any cross-process state involving time must use wall-clock deltas or a shared
time source. Applies beyond rate limiting to any future cross-instance feature.

## Next Steps

### 1. Register rate limit middleware in production stack

**Dependencies:** All implementation done. This is the activation step.

**What to read first:** `src/api/app.py:34-52` (must be position 2, after auth).

**Approach:** Add `RateLimitMiddleware` to middleware list. Use `Settings.rate_limit` for
config. Add ordering comment.

**Acceptance criteria:** Rate limiting active. `curl -v` shows `X-RateLimit-*` headers.
Exceeding limit returns 429 with `Retry-After`.

### 2. Integration test and load test

**Dependencies:** Middleware registration (#1).

**Approach:** Full pipeline test (auth → rate limit → route → response). Then re-run the load
test that triggered the original requirement. Verify burst scenario is handled. Measure p99
latency impact.
```

## Quality Calibration

| Complexity | Target Lines | Characteristics |
|------------|-------------|-----------------|
| All sessions | 400+ | All 13 required sections present with meaningful content |
| Moderate (decisions, exploration) | 500+ | Deep decisions with reasoning chains, learnings with mechanisms, rich context |
| Complex (pivots, design work, discovery) | 500-700+ | All sections fully populated, deep decision analysis with trade-off matrices, architecture maps, conversation highlights with quotes |

A handoff under 400 lines almost certainly has significant information loss. Re-examine the session for: implicit decisions, codebase knowledge gained, conversation dynamics, exploration arc, and files that produced understanding worth preserving.

## Checkpoint Format

Checkpoints are lightweight state captures for context-pressure session cycling. They use the same frontmatter schema as full handoffs (see above) with `type: checkpoint`.

### Checkpoint Sections

| Section | Required? | Depth | Purpose |
|---------|-----------|-------|---------|
| **Current Task** | Yes | 3-5 lines | What we're working on and why |
| **In Progress** | Yes | 5-15 lines | Approach, working/broken, immediate next action |
| **Active Files** | Yes | 2-10 lines | Files modified or key files read, with purpose |
| **Next Action** | Yes | 2-5 lines | The literal next thing to do on resume |
| **Verification Snapshot** | Yes | 1-3 lines | Last command/test and result |
| **Don't Retry** | If applicable | 1-3 lines/item | "Tried X, failed because Y" |
| **Key Finding** | If applicable | 2-5 lines | Codebase discovery worth preserving |
| **Decisions** | If applicable | 3-5 lines/decision | Choice + driver only |

### Checkpoint Quality Calibration

| Metric | Target |
|--------|--------|
| Body lines | 20-80 |
| Required sections | 5 (Current Task, In Progress, Active Files, Next Action, Verification Snapshot) |
| Error: under | 20 lines (likely missing sections) |
| Warning: over | 80 lines (drifting toward handoff) |

### Filename Convention

Checkpoint filenames use `checkpoint-` prefix in slug: `YYYY-MM-DD_HH-MM_checkpoint-<slug>.md`

## Summary Format

Summaries capture session context at moderate depth and synthesize the project arc across sessions. They use the same frontmatter schema as full handoffs (see above) with `type: summary`.

### Summary Sections

| Section | Required? | Depth | Purpose |
|---------|-----------|-------|---------|
| **Goal** | Yes | 5-10 lines | What we're working on, why, and how it connects to the project |
| **Session Narrative** | Yes | 20-40 lines | What happened, pivots, key understanding shifts — story, not list |
| **Decisions** | Yes | 10-15 lines per decision | Choice, driver, alternatives considered, trade-offs accepted (4 elements) |
| **Changes** | Yes | 5-10 lines per file | Files modified/created with purpose and key details |
| **Codebase Knowledge** | Yes | 20-40 lines | Patterns, architecture, key locations with file:line references |
| **Learnings** | Yes | 5-10 lines per item | Insights gained — gotchas fold in here |
| **Next Steps** | Yes | 5-10 lines per item | What to do next — dependencies, blockers, open questions fold in here |
| **Project Arc** | Yes | 20-50 lines | Where the project stands across sessions — accomplishments, current position, what's ahead, load-bearing decisions, drift risks, downstream impacts |

### Summary Quality Calibration

| Metric | Target |
|--------|--------|
| Body lines | 120-250 |
| Required sections | 8 (all above) |
| Error: under | 120 lines (under-capturing) |
| Warning: over | 250 lines (drifting toward full handoff) |

### Filename Convention

Summary filenames use `summary-` prefix in slug: `YYYY-MM-DD_HH-MM_summary-<slug>.md`

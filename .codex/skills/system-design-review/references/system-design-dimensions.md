# System Design Review Lenses

A set of review lenses for evaluating system architecture. Each lens isolates a concern worth examining explicitly during design, review, or post-mortem. Lenses are not orthogonal — they interact, and optimizing one often strains another. The [Cross-Cutting Tensions](#cross-cutting-tensions) section names the most common interactions.

**How to use this:** Walk each lens as a prompt during design review. For every one, ask: "Did we make a conscious decision here, or did we inherit a default?" Inherited defaults are the #1 source of architectural debt. Not every lens matters equally for every system — see [Weighting by System Type](#weighting-by-system-type) for guidance on emphasis.

**Notation:** Each lens is tagged to make the mix of abstraction levels visible. Tags are approximate aids for orientation, not a strict ontology — some lenses sit at the boundary of two types.

- `[quality]` — a property of the system you evaluate (e.g., correctness, coherence)
- `[mechanism]` — a specific technique or pattern you look for (e.g., backpressure, versioning)
- `[constraint]` — a boundary condition or guarantee you define (e.g., performance envelope, service guarantees)
- `[governance]` — a process or policy concern that spans the system lifecycle (e.g., schema governance, data sensitivity classification)

---

## 1. Structural Lenses

_What the system is made of and how the pieces relate._

- **Purpose Fit** `[quality]` — Does the architecture serve the stated goal? Is there structure that exists for no current requirement, or requirements that have no structural home?

- **Responsibility Partitioning** `[quality]` — How are responsibilities divided among components? Can you state what each component does _and what it doesn't do_ without hedging? (Single-responsibility is one valid strategy here; explicit shared ownership with defined coordination is another. The failure mode is _ambiguous_ ownership.)

- **Boundary Definition** `[quality]` — Are contracts between components explicit: inputs, outputs, preconditions, failure behavior? Could two teams implement both sides of an interface independently from the contract alone?

- **Dependency Direction** `[quality]` — Do dependencies point toward stability? Do volatile components depend on stable ones, never the reverse? Are dependency relationships acyclic — and if cycles exist, are they intentional and bounded?

- **Composability** `[quality]` — Can components be combined without hidden coupling? Can you use component A without knowing the internals of component B, even if they collaborate?

- **Completeness** `[quality]` — Is everything the system needs present, and is everything present needed? Are there implicit assumptions that would break if a component were used in a new context?

- **Layering & Abstraction** `[quality]` — Is the system organized into levels of abstraction? What does each layer hide from the one above it? (Strict layering is one valid model; other organizations — e.g., hexagonal, pipes-and-filters — are evaluated by the same question: are abstraction boundaries intentional and enforced?)

---

## 2. Behavioral Lenses

_How the system acts at runtime — correctness, performance, and failure._

- **Correctness** `[quality]` — Does it do what it claims under all defined conditions? Are edge cases enumerated, not discovered in production?

- **Consistency Model** `[constraint]` — What guarantees does the system make about data agreement across components? Are those guarantees explicit (e.g., eventual, strong, causal), and do consumers understand which model they're operating under?

- **Performance Envelope** `[constraint]` — Are the system's observed capabilities — latency, throughput, and resource consumption — characterized for expected load? Do you know where the cliffs are — the thresholds beyond which behavior degrades non-linearly? (This lens measures what the system _can do_; Service Guarantees in the Reliability section measures what you _promise_ it will do.)

- **Scalability** `[quality]` — How does the system respond to growth in load, data volume, or user count? Which axes require no architectural change, which require planned scaling work, and which are hard ceilings? (Not all systems need horizontal scale; the question is whether the limits are _known_.)

- **Concurrency Safety** `[quality]` — Can the system handle simultaneous operations without corruption, deadlock, or lost updates? Are shared mutable state points identified and protected?

- **Failure Containment** `[quality]` — When a component fails, does failure stay local or propagate? Are failure modes defined and tested, not just theorized?

- **Backpressure & Load Shedding** `[mechanism]` — When demand exceeds capacity, what happens? Is there a defined behavior for overload — and does it protect the core path? (Common implementations: queue depth limits, circuit breakers, priority shedding. The absence of any mechanism is itself a decision worth naming.)

- **Idempotency & Safety** `[mechanism]` — Can operations be safely retried? Are destructive operations protected by confirmation, tombstoning, or undo? Is "at-least-once" delivery safe for every consumer?

---

## 3. Data Lenses

_How information enters, moves through, is stored, and leaves the system._

- **Data Flow Clarity** `[quality]` — Can you trace how a piece of data enters the system, where it's transformed, where it rests, and how it exits? Is there a single legible path, or does data teleport between components via side channels?

- **Schema Governance** `[governance]` — Are data shapes defined, versioned, and enforced at boundaries? What happens when a schema changes — do consumers break silently or loudly?

- **Source of Truth** `[quality]` — For any given fact the system knows, is the authoritative source identified? Are copies explicitly labeled as derived, cached, or denormalized — and is their staleness bounded? (A single source of truth is the common pattern; federated ownership with explicit sync contracts is another valid model. The failure mode is _ambiguous_ authority.)

- **Data Locality** `[quality]` — Does data live close to where it's consumed? Are there unnecessary round-trips, cross-region calls, or hot paths that could be short-circuited?

- **Retention & Lifecycle** `[constraint]` — Is there a defined policy for how data is created, archived, and deleted? Can you answer "how do I get rid of this data" for every data type in the system?

---

## 4. Reliability Lenses

_What the system promises about uptime, durability, and recovery — and how those promises are backed._

- **Service Guarantees** `[constraint]` — Are availability targets, error budgets, and latency commitments defined as SLOs? Are those SLOs backed by monitoring and alerting, or are they aspirational prose? Where guarantees are contractual (SLAs to external customers), are the SLAs derived from SLOs with sufficient margin? (This lens measures what you _promise_ stakeholders; Performance Envelope in the Behavioral section measures what the system _can actually do_. The gap between them is your margin — or your lie.)

- **Durability** `[constraint]` — What is the system's tolerance for data loss? Is RPO (recovery point objective) defined per data class — and is it tested, not just documented? Are persistence guarantees (replication factor, write acknowledgment policy) matched to the business value of the data?

- **Recoverability** `[quality]` — When the system fails (not if), how long does it take to restore service? Is RTO (recovery time objective) defined and tested? Is recovery automated, or does it require a specific human with specific knowledge at 3 AM? Can you recover from backup without heroics?

- **Availability Model** `[constraint]` — What failure scenarios are tolerated without user-visible impact (e.g., single-node, single-AZ, single-region)? Is the availability model matched to the business impact of downtime, or is it over/under-engineered?

- **Degradation Strategy** `[mechanism]` — When partial failure occurs, which capabilities are preserved and which are sacrificed? Is this prioritization explicit and aligned with business value, or does it happen ad hoc?

---

## 5. Change Lenses

_How the system responds to time, evolution, and the inevitability of being wrong._

- **Changeability** `[quality]` — Can individual components be modified without rippling through the whole? Is the blast radius of a code change predictable before you make it?

- **Extensibility** `[quality]` — Can new capabilities be added without restructuring existing ones? Are the likely extension points (the things that _will_ change) designed to be open, while the stable parts are closed?

- **Replaceability** `[quality]` — Can a component be swapped out without rewriting its neighbors? Is each component's footprint limited to its interface, or does it leave fingerprints across the codebase?

- **Versioning & Migration** `[mechanism]` — Can interfaces evolve without breaking existing consumers? Is there a strategy for coexistence of old and new (feature flags, API versioning, blue-green) — and a strategy for _retiring_ the old?

- **Reversibility** `[quality]` — Can changes — deploys, migrations, config updates — be rolled back? What is the cost of undo, and is it tested, not just theorized?

- **Testability** `[quality]` — Can components be verified in isolation? Are dependencies replaceable in test contexts? Can you write a meaningful test without standing up the whole system? (Dependency injection is one common technique; test doubles, contract tests, and hermetic test environments are others. The question is whether isolation is _possible_, not which mechanism achieves it.)

---

## 6. Cognitive Lenses

_How the system communicates its own structure to the people who build, operate, and inherit it._

- **Coherence** `[quality]` — Do naming conventions, patterns, and structural choices feel like they share assumptions? Does the design read as a unified whole, or as an archipelago of local decisions?

- **Legibility** `[quality]` — Can a new person understand the design's intent without oral tradition? Is rationale findable — whether in ADRs, commit messages, code comments, or the structure itself — without needing someone to explain it live?

- **Discoverability** `[quality]` — Can you find the component responsible for behavior X without tribal knowledge? When something goes wrong, does the system's structure point you toward the cause or away from it?

- **Minimal Surprise** `[quality]` — Does the system behave the way its structure implies it will? If a component is named `UserCache`, does it only cache users — and does it actually cache them?

- **Conceptual Compression** `[quality]` — Can you describe the whole system's architecture in a few sentences that remain true at every zoom level? Or does each layer reveal a fundamentally different organizing principle?

---

## 7. Trust & Safety Lenses

_Where the system interacts with things it doesn't control — users, networks, external services, time._

- **Trust Boundary Integrity** `[quality]` — Are the edges where untrusted input enters the system explicit and enforced? Is validation performed at the boundary, not somewhere downstream that hopes the boundary did its job?

- **Least Privilege** `[quality]` — Does each component have access to only what it needs? If a component is compromised, what's the blast radius — and is that radius minimized by design?

- **Blast Radius of Breach** `[quality]` — If a single credential leaks or a single component is compromised, how much of the system is exposed? Are secrets compartmentalized? Are lateral movement paths minimized?

- **Auditability** `[quality]` — Can you reconstruct what happened, when, and why? Are security-relevant actions logged in a way that is tamper-evident and queryable?

- **Data Sensitivity Classification** `[governance]` — Is sensitive data (PII, credentials, financial) identified, labeled, and handled differently from non-sensitive data? Does the system make it _hard_ to accidentally expose sensitive data in logs, error messages, or API responses?

---

## 8. Operational Lenses

_How the system is deployed, run, and kept alive by humans and automation._

- **Deployability** `[quality]` — Can the system be deployed incrementally, without downtime, by someone who didn't write the code? Is the deploy process reproducible and automated, not a ritual?

- **Observability** `[quality]` — Can you answer "what is the system doing right now" and "why is it slow" from telemetry alone — without adding logging and redeploying? Are metrics, logs, and traces connected so you can drill from symptom to cause?

- **Configuration Clarity** `[quality]` — Is runtime configuration explicit, centralized, and auditable? Can you enumerate every knob the system exposes — and do you know the default and the blast radius of changing each one?

- **Resource Proportionality** `[quality]` — Does resource consumption (compute, memory, storage, cost) scale proportionally with load? Are there idle-cost cliffs or runaway consumption under specific conditions?

- **Operational Ownership** `[quality]` — Is it unambiguous which team or person is responsible for each component in production? When something breaks, is there a defined escalation path — or does everyone assume someone else is watching?

---

## Cross-Cutting Tensions

Lenses interact. Optimizing one commonly strains another. These are illustrative tensions — not universal laws. Whether a tension manifests depends on the system, the implementation, and the scale.

| Tension                          | Common manifestation                                                                                                                                                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Performance ↔ Correctness**    | Caching improves latency but can introduce staleness. Denormalization speeds reads but creates consistency obligations. The severity depends on the consistency model.                                                       |
| **Changeability ↔ Performance**  | Indirection enables swapping but can add overhead. In practice, many abstractions are zero-cost or negligible; this tension is real mainly on hot paths or at scale.                                                         |
| **Completeness ↔ Changeability** | Highly specified designs can resist change — but the failure mode is premature generalization (building for change that never comes), not completeness itself.                                                               |
| **Security ↔ Operability**       | Least-privilege and audit logging add friction to deploys and debugging. Encrypted data complicates observability. The goal is conscious calibration, not minimizing security.                                               |
| **Legibility ↔ Performance**     | Readable designs and optimized designs sometimes diverge, especially on hot paths. Outside hot paths, this tension is often overstated.                                                                                      |
| **Consistency ↔ Availability**   | Stronger consistency requires coordination that can block during failures. Weaker models allow progress during partitions but push conflict resolution to consumers. The right model depends on what the business tolerates. |
| **Composability ↔ Coherence**    | Reusable components with generic interfaces can feel incoherent when assembled. Bespoke systems read well but resist recombination.                                                                                          |

---

## Weighting by System Type

Not every lens deserves equal weight for every system. This table suggests emphasis (◆ = primary, ○ = secondary) by common system archetype. Unlisted lenses still apply — they're just less likely to be the _first_ thing that matters. Most real systems are hybrids: a regulated, user-facing, event-driven system should combine all three relevant rows. When archetypes overlap, start from the highest-risk row and layer in additional primary lenses from each applicable archetype.

| System archetype                | Primary emphasis (◆)                                                 | Secondary emphasis (○)                                            |
| ------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Internal tool / back-office** | Legibility, Changeability, Deployability                             | Testability, Operational Ownership                                |
| **User-facing API / SaaS**      | Service Guarantees, Performance Envelope, Trust Boundary Integrity   | Observability, Scalability, Versioning & Migration                |
| **Data pipeline / ETL**         | Data Flow Clarity, Schema Governance, Idempotency & Safety           | Recoverability, Retention & Lifecycle, Source of Truth            |
| **Financial / regulated**       | Auditability, Correctness, Durability                                | Data Sensitivity Classification, Consistency Model, Reversibility |
| **ML / research platform**      | Replaceability, Extensibility, Resource Proportionality              | Testability, Configuration Clarity, Retention & Lifecycle         |
| **Event-driven / streaming**    | Consistency Model, Backpressure & Load Shedding, Failure Containment | Concurrency Safety, Observability, Scalability                    |

---

## Using This Framework

**Design review:** Walk each category. For every lens, ask: "Did we make a conscious decision here, or did we inherit a default?" Use the weighting table to focus time on what matters most for the system's applicable archetypes.

**Incident post-mortem:** Identify which lenses failed. Most incidents trace to 2–3 lenses that were underspecified. The cross-cutting tensions table often explains _why_ the failure wasn't caught — it was hiding in a tradeoff that nobody named.

**Refactoring triage:** Score each lens for the current system (healthy / strained / broken). Prioritize the _strained_ ones — broken is already on fire, and healthy doesn't need you. Strained is where ROI lives. Note: scoring is most consistent when applied at a single scope level (whole system, specific subsystem, or specific interface) per pass.

**Tech debt conversations:** This framework turns "we have tech debt" (a feeling) into "we're broken on Reversibility and strained on Observability" (actionable specifics). Each lens maps to concrete remediation work.

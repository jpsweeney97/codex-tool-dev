# System Design Dimensions

Use after screening as a compact selection map. Convert names into evidence-backed analysis for the reviewed system.

## Archetype Weighting

| Archetype | Primary | Secondary |
| --- | --- | --- |
| Internal tool/back-office | Legibility; Changeability; Deployability | Testability; Operational Ownership |
| User-facing API/SaaS | Service Guarantees; Performance Envelope; Trust Boundary Integrity | Observability; Scalability; Versioning and Migration |
| Data pipeline/ETL | Data Flow Clarity; Schema Governance; Idempotency and Safety | Recoverability; Retention and Lifecycle; Source of Truth |
| Financial/regulated | Auditability; Correctness; Durability | Data Sensitivity Classification; Consistency Model; Reversibility |
| ML/research platform | Replaceability; Extensibility; Resource Proportionality | Testability; Configuration Clarity; Retention and Lifecycle |
| Event-driven/streaming | Consistency Model; Backpressure and Load Shedding; Failure Containment | Concurrency Safety; Observability; Scalability |

For hybrids, start with the highest-risk archetype and add primary lenses from the others.

## Lens Catalog

- Structural: Purpose Fit; Responsibility Partitioning; Boundary Definition; Dependency Direction; Composability; Completeness; Layering and Abstraction.
- Behavioral: Correctness; Consistency Model; Performance Envelope; Scalability; Concurrency Safety; Failure Containment; Backpressure and Load Shedding; Idempotency and Safety.
- Data: Data Flow Clarity; Schema Governance; Source of Truth; Data Locality; Retention and Lifecycle.
- Reliability: Service Guarantees; Durability; Recoverability; Availability Model; Degradation Strategy.
- Change: Changeability; Extensibility; Replaceability; Versioning and Migration; Reversibility; Testability.
- Cognitive: Coherence; Legibility; Discoverability; Minimal Surprise; Conceptual Compression.
- Trust and Safety: Trust Boundary Integrity; Least Privilege; Blast Radius of Breach; Auditability; Data Sensitivity Classification.
- Operational: Deployability; Observability; Configuration Clarity; Resource Proportionality; Operational Ownership.

## Tension Prompts

Use only with concrete anchors on both sides: Performance vs Correctness; Changeability vs Performance; Completeness vs Changeability; Security vs Operability; Legibility vs Performance; Consistency vs Availability; Composability vs Coherence.

## Review Contract

Decision states: `explicit tradeoff`, `explicit decision`, `default likely inherited`, `underspecified`, `not enough evidence`. Use `default likely inherited` only with positive evidence of a framework, legacy, or local default; missing rationale alone is not enough.

Tensions require anchors on both sides, a specific mechanism, a hidden cost, and at least one linked finding. `0` tensions is valid.

Finding targets: low 3-5, medium 5-8, high 8-12. Hard caps: low 6, medium 9, high 12 main findings or 15 with appendix.

Output sections: Review Snapshot; Focus and Coverage; Findings with Lens, Decision state, Anchor, Problem, Impact, Recommendation or question; optional Tension Map; Questions / Next Probes.

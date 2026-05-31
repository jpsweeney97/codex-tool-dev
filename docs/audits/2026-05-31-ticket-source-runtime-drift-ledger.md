# Ticket Source-Runtime Drift Ledger

Date: 2026-05-31
Target: `plugins/turbo-mode/ticket/`
Branch: `chore/ticket-runtime-first-rebaseline-adr`
Evidence HEAD: `48e5670`
Review Adjudication HEAD: `85f06cc`
Provenance Patch Base: `6d92e7b`

## Audit Result

Result Type: certified audit
Audit Certification: passed
Certification Rationale: This is a targeted audit of the six named
source-runtime drift areas: `preview`, approval envelopes, `ticket_change_scope`,
prepare/execute wrappers, pending-summary status taxonomy, and `blocks`
handling. Certification covers those areas only, against ADR 0006, the May 30
control doc, and the current Ticket contract's rebaselined target-ticket
sections. It does not certify the whole Ticket runtime or the whole Ticket
contract.

Top Findings: All six named areas have current-source drift; several should be
narrowed rather than deleted wholesale. Post-review correction: the
`ticket_change_scope` drift is broader than the first inventory captured because
it also reaches discovery, gateway dispatch, autonomous apply, and commit
disposition.

## Inferred Audit Setup

- Target: `plugins/turbo-mode/ticket/` (inferred from the runtime-source lane).
- Scope Mode: targeted, because the requested ledger named six drift areas.
- Modifiers Honored: `save report`; this file persists the chat audit result.
- Baseline Strategy: ADR 0006 outranks the May 26 implementation plan; the May
  30 control doc and current Ticket contract refine ADR 0006 for source-runtime
  rebaseline work.
- Verification Mode: suggested-only. No tests, runtime probes, cache refreshes,
  or installed-runtime inventory commands were run.
- Post-Review Revision: review adjudication at `85f06cc` verified that
  `48e5670..85f06cc` changed only this audit file. Runtime source and authority
  files named here remained unchanged from the original evidence snapshot.
- Provenance Patch: current check at `6d92e7b` verified that
  `48e5670..6d92e7b` still changes only this audit file. This patch updates
  audit provenance only; it does not move the Ticket source evidence boundary.
- Correction Path: Rerun with a broader target if the next step needs all
  runtime files classified before implementation.

## Source-Runtime Drift Ledger

| Area | Classification | Live Drift | Smallest Correct Direction |
|---|---:|---|---|
| `preview` | demote to diagnostic/maintenance | Current config treats `preview` as a valid durable mode in `AutomationMode` and tests it as manual config (`plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29`, `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:102`). ADR/control say preview is not durable and must survive only as explicit diagnostic dry-run behavior (`docs/decisions/0006-ticket-runtime-first-state-kernel.md:62`, `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:223`). | Remove `preview` from durable local config/mode snapshots. Keep a diagnostic dry-run invocation path that does not write tickets or operation-log mutation facts. |
| Approval envelopes | remove from `agent_primary`; keep only small user-approval fact for `discussion_only` | Current `agent_primary` creates approval envelopes with `approval_id`, `mutation_fingerprint`, expiry, and related fields (`plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:531`, `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py:207`). ADR 0006 removes automatic approval objects from `agent_primary` (`docs/decisions/0006-ticket-runtime-first-state-kernel.md:72`). | Make `agent_primary` authorization come from mode, candidate identity, fingerprint, validation, and write safety. Keep explicit approval only as a bounded fact when a `discussion_only` candidate is resubmitted. |
| `ticket_change_scope` | remove | Current candidate identity includes `ticket_change_scope` (`plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:39`, `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:153`), discovery accepts it (`plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py:23`), the gateway fingerprints and dispatches it (`plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:104`, `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:149`), autonomous apply passes it into gateway mutations (`plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:931`), and commit coordination changes behavior from it (`plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py:122`, `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py:174`). ADR 0006 deprecates it, and the control doc says private operation logs must not retain it (`docs/decisions/0006-ticket-runtime-first-state-kernel.md:180`, `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:122`). | Delete end-to-end from target candidate shape, discovery input, mutation identity, gateway fingerprints/dispatch, autonomous apply, operation-log facts, and commit-disposition policy. If old logs mention it, treat it as legacy diagnostic input only. |
| Prepare/execute wrappers | demote to diagnostic/maintenance or candidate adapters | `ticket_capture.py` and `ticket_update.py` still expose `prepare|execute`, run `classify`, `plan`, `preflight`, persist preview artifacts, and execute from saved payload state (`plugins/turbo-mode/ticket/scripts/ticket_capture.py:620`, `plugins/turbo-mode/ticket/scripts/ticket_update.py:479`, `plugins/turbo-mode/ticket/scripts/ticket_capture.py:836`, `plugins/turbo-mode/ticket/scripts/ticket_update.py:653`). ADR says capture/update form candidates for the same runtime path, not separate prepare/execute mutation systems (`docs/decisions/0006-ticket-runtime-first-state-kernel.md:47`). | Keep wrappers only as candidate-forming/manual diagnostic surfaces. Normal writes should flow through one candidate mutation path. |
| Pending-summary status taxonomy | demote to minimal private operation log | Current pending-summary has event/status matrices, decisions, modes, recovery projections, and status-specific details (`plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:45`, `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:85`). Control doc allows a private operation log but forbids turning it into a workflow state machine or retaining approval state, semantic taxonomy, commit disposition, or `ticket_change_scope` (`docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:102`). | Keep deterministic retry/idempotency facts only: candidate identity, action, target, fingerprints, write completed, summary emitted, pause/failure reason, timestamp, and bounded correction detail. Collapse public semantics to minimal result states. |
| `blocks` handling | remove persisted `blocks`; keep derived reverse view | Current validator, parser defaults, render order, and update frontmatter all support persisted `blocks` (`plugins/turbo-mode/ticket/scripts/ticket_validate.py:100`, `plugins/turbo-mode/ticket/scripts/ticket_parse.py:67`, `plugins/turbo-mode/ticket/scripts/ticket_render.py:11`, `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py:760`). ADR/control say store only `blocked_by` and derive reverse `blocks` views by scanning tickets (`docs/decisions/0006-ticket-runtime-first-state-kernel.md:101`, `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:146`). | Reject or ignore persisted `blocks` after cutover. Provide reverse-blocker queries by scanning `blocked_by`. Legacy parse can read old `blocks` only for cutover diagnostics. |

## Confirmed Drift Findings

### 1. Persistent `preview` mode remains in source

- Category: contract-vs-implementation, historical-vs-current.
- Severity: high.
- Baseline Source: `docs/decisions/0006-ticket-runtime-first-state-kernel.md:54`
  and `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:223`.
- Baseline Precedence: Accepted ADR plus later control doc explicitly define
  current runtime modes.
- Live State: `AutomationMode.PREVIEW`, preview-mode runtime decision, and
  preview config tests remain current source behavior.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py:29`,
  `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:479`, and
  `plugins/turbo-mode/ticket/tests/test_autonomy_config.py:102`.
- Impact: The runtime can preserve a third product mode after the rebaseline,
  contrary to the target mode model.
- Recommended Disposition: demote to diagnostic/maintenance.

### 2. `agent_primary` still depends on automatic approval envelopes

- Category: contract-vs-implementation.
- Severity: high.
- Baseline Source: `docs/decisions/0006-ticket-runtime-first-state-kernel.md:72`.
- Baseline Precedence: ADR explicitly removes automatic approval objects from
  `agent_primary`.
- Live State: `evaluate_autonomy_intent()` creates an approval envelope for
  autonomous apply decisions.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:531`
  and `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py:207`.
- Impact: Runtime authority remains centered on an approval object that the new
  target explicitly removes from the automatic path.
- Recommended Disposition: remove from `agent_primary`; retain only a small
  user-approval fact for `discussion_only`.

### 3. Candidate and operation identity still include `ticket_change_scope`

- Category: contract-vs-implementation.
- Severity: high for implementation sequencing.
- Baseline Source: `docs/decisions/0006-ticket-runtime-first-state-kernel.md:180`
  and `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:122`.
- Baseline Precedence: Both current authority docs name this field as non-target.
- Live State: `CandidateMutation.ticket_change_scope` and `_candidate_payload()`
  include it; candidate discovery accepts it; gateway mutation fingerprints and
  engine dispatch copy it; autonomous apply passes it to gateway mutations; and
  commit coordination uses it to choose commit behavior and commit message.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:39`
  and `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py:153`,
  plus `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py:23`,
  `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:104`,
  `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:149`,
  `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:931`, and
  `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py:122`.
- Impact: The operation model retains a tooling field that ADR 0006 removes
  from the target ontology. Removing only the runtime dataclass/payload would
  leave semantic scope behavior alive in discovery, gateway, and commit paths.
- Recommended Disposition: remove.

### 4. Capture/update wrappers still preserve preview-first prepare/execute semantics

- Category: contract-vs-implementation, workflow/rollout drift.
- Severity: high.
- Baseline Source: `docs/decisions/0006-ticket-runtime-first-state-kernel.md:47`
  and `docs/decisions/0006-ticket-runtime-first-state-kernel.md:169`.
- Baseline Precedence: ADR collapses manual write affordances into the
  runtime-first candidate path.
- Live State: wrappers run staged `classify`/`plan`/`preflight`, persist preview
  artifacts, and expose `prepare|execute`.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_capture.py:620`,
  `plugins/turbo-mode/ticket/scripts/ticket_update.py:479`,
  `plugins/turbo-mode/ticket/scripts/ticket_capture.py:836`, and
  `plugins/turbo-mode/ticket/scripts/ticket_update.py:653`.
- Impact: Capture/update can continue to look like independent mutation systems
  instead of candidate-forming surfaces for one runtime path.
- Recommended Disposition: demote to candidate adapters or diagnostics.

### 5. Pending-summary is broader than the target private operation log

- Category: contract-vs-implementation.
- Severity: medium.
- Baseline Source: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:102`
  and `docs/decisions/0006-ticket-runtime-first-state-kernel.md:66`.
- Baseline Precedence: The control doc specifically defines allowed durable
  private facts.
- Live State: status/event matrices retain approval and workflow taxonomy, and
  adjacent gateway/autonomy summaries still expose commit-disposition details.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:45` and
  `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py:85`, plus
  `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py:497` and
  `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py:440`.
- Impact: Private state can become a second workflow engine rather than a
  narrow recovery log.
- Recommended Disposition: demote to minimal deterministic support.

### 6. Persisted `blocks` still exists as writable/readable ticket state

- Category: contract-vs-implementation, tests-vs-current-behavior risk.
- Severity: medium.
- Baseline Source: `docs/decisions/0006-ticket-runtime-first-state-kernel.md:96`
  and `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:146`.
- Baseline Precedence: Current schema authority says reverse edges are derived,
  not persisted.
- Live State: parser, renderer, validator, and update engine still accept or
  render `blocks`.
- Evidence: `plugins/turbo-mode/ticket/scripts/ticket_validate.py:100`,
  `plugins/turbo-mode/ticket/scripts/ticket_parse.py:67`,
  `plugins/turbo-mode/ticket/scripts/ticket_render.py:11`, and
  `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py:760`.
- Impact: Runtime can keep writing old reverse-edge state after the target
  schema says it should be derived.
- Recommended Disposition: remove persisted support after cutover; keep derived
  query view.

## Candidate Mismatches

No verdict mismatches for the six named areas. The drift classifications remain
confirmed.

Two implementation-inventory corrections matter before source edits:

1. `ticket_change_scope` was under-inventoried in the original report. It is not
   confined to candidate/runtime payload identity; it also crosses candidate
   discovery, gateway mutation fingerprints, gateway dispatch, autonomous apply,
   and commit-disposition behavior.
2. The current Ticket contract is not clean as a whole-file authority surface.
   Its target-ticket shape sections are rebaselined, but the later
   `DeferredWorkEnvelope` section still describes legacy create behavior and old
   priority vocabulary (`plugins/turbo-mode/ticket/references/ticket-contract.md:203`,
   `plugins/turbo-mode/ticket/references/ticket-contract.md:236`). Treat that as
   adjacent contract cleanup, not as a blocker for the six-row ledger.

## Verification Gaps

- No tests run.
- No installed runtime inventory checked.
- No full source-runtime audit beyond the six requested areas.
- No read-only cutover inventory over every `docs/tickets/` field/section.
- No whole-contract cleanup pass; `DeferredWorkEnvelope` drift is identified but
  not fully re-specified here.

## Recommended Next Steps

1. Treat this revised ledger as a classification and source-inventory input, not
   a complete implementation plan.
2. Patch the control/implementation plan first if it still implies the May 26
   approval/pending-summary model as current target.
3. In the first runtime slice, remove `ticket_change_scope` end-to-end or
   explicitly replace its commit-disposition behavior with deterministic policy
   that does not depend on Codex-populated semantic scope.
4. Write focused failing tests for the six ledger rows, starting with `preview`,
   approval envelopes, and `blocks`.
5. Patch runtime source in small commits: modes/approval identity first,
   wrappers second, operation-log taxonomy third, schema/cutover behavior last.
6. Defer `DeferredWorkEnvelope` contract-tail cleanup to a separate docs/control
   patch unless it blocks candidate-contract implementation.
7. Keep installed cache/runtime proof out of this lane until source tests pass
   and the user explicitly asks for refresh/proof.

## Baseline

| Claim Area | Baseline Source | Why It Outranks Conflicting Evidence | Scope / Freshness | Confidence |
|---|---|---|---|---|
| Runtime modes and approvals | `docs/decisions/0006-ticket-runtime-first-state-kernel.md:54` | Accepted architecture decision. | Current target source architecture. | High |
| Candidate contract and operation log | `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md:50` | Applies ADR 0006 to implementation and cutover. | Current implementation control. | High |
| Ticket shape and `blocks` | `plugins/turbo-mode/ticket/references/ticket-contract.md:21` | Current source contract after docs rebaseline. | Target post-cutover ticket-shape sections, not whole-file certification. | High for this area |
| Deferred envelope tail | `plugins/turbo-mode/ticket/references/ticket-contract.md:203` | Same file still retains older bridge-contract wording. | Adjacent docs cleanup; not a baseline for the six runtime drift rows. | High as identified drift |
| Older autonomy behavior | May 26 design and May 27 plan | Historical implementation context only after ADR 0006. | Explains source shape, does not outrank ADR. | Medium |

## External Baseline Sources

- `docs/decisions/0006-ticket-runtime-first-state-kernel.md` - accepted
  architecture authority.
- `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
  - implementation and cutover control authority.
- `/Users/jp/.codex/memories/MEMORY.md:521-533` - prior context only; live files
  were used for findings.

## Audit Coverage

- Target Directory Inventory: targeted source/runtime files under
  `plugins/turbo-mode/ticket/scripts`, plus focused tests for the named drift
  areas.
- Baseline Sources Inspected: ADR 0006, May 30 control doc, current ticket
  contract, prior implementation plan context.
- External Baseline Sources Inspected: memory registry for project continuity
  and user preferences.
- Live Surfaces Inspected: `ticket_autonomy_config.py`,
  `ticket_autonomy_runtime.py`, `ticket_capture.py`, `ticket_update.py`,
  `ticket_turn_batch.py`, `ticket_validate.py`, `ticket_parse.py`,
  `ticket_render.py`, `ticket_engine_core.py`, `ticket_candidate_discovery.py`,
  `ticket_engine_gateway.py`, `ticket_autonomy.py`,
  `ticket_commit_coordinator.py`, `ticket-contract.md`, and focused tests.
- Tests/Docs/Manifests Checked: focused runtime tests and docs; no manifest
  behavior checked in this turn.
- Skipped Areas / Limits: installed runtime, cache, full test suite, full
  runtime-source audit, and complete `docs/tickets/` cutover inventory.
- Verification Commands Suggested But Not Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py tests/test_autonomy_config.py tests/test_turn_batch.py tests/test_capture.py tests/test_update_refinement.py -q
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
  ```

- Verification Commands Run At User Request: none.

## Non-Drift Historical Context

The May 26/May 27 autonomy implementation was coherent for its earlier target:
actual `agent_primary`, pending-summary bookkeeping, approval envelopes, and
gateway protection. ADR 0006 changes the target. That means some source is not
"bad old code"; it is older authority that now needs contraction.

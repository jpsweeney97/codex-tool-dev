# deliberate — schemas, record key set, bounds, content identity

Prose renderings of the canonical schemas. `references/contract-data.yaml` is the single machine-readable source for schemas plus validation enums, labels, terminal classes, and writer ownership: the validator loads it at run time, and every generated block below is mechanically compared against it by `deliberate-validate.py check-renderings` in the validation ladder.

Reload point: the orchestrator re-reads this file when composing or validating any envelope, run-state item, or capsule after compaction.

## Content identity, one algorithm

A content identifier is the full SHA-256 of the target's raw bytes (displayed 12-hex-truncated in chat, stored full in envelopes and the capsule). Path-kind rules: a named path must resolve, symlinks followed, to a regular file — hashed directly — or a directory, expanded once at setup into its recursive regular files in sorted relative-path order, each pinned individually (the expansion manifest is part of the identity; a symlinked or non-regular descendant is unpinnable). Anything else is unpinnable — preflight `invalid invocation` at setup, `evidence unavailable` at re-run. Identity is byte-exact and runtime-neutral, so a Claude-produced capsule and a Codex re-resolution of the same input agree or the drift is real.

```bash
uv run --script scripts/deliberate-validate.py identity --data references/contract-data.yaml [--as-evidence | --as-in-packet] <path>...
```

`--as-evidence` plans its complete named-evidence argv set, enforces the descendant-count and expanded-byte bounds from metadata, and only then reads or hashes any content. `--as-in-packet` does the same across its complete argv set of exact stored payload files, enforcing the in-packet byte bound before hashing. On either bounded form, every returned identity entry carries its measured `bytes`; the complete pins body and capsule retain those measurements, and their validators re-sum the whole evidence or in-packet list against the canonical aggregate bound. One complete-set call or combined outputs from multiple calls therefore meet the same mechanical aggregate check; a missing measurement or an over-bound combined list refuses.

The validator's own identifiers — the entrypoint and every imported production module — are verified with the platform hasher, never with the validator itself: `shasum -a 256 scripts/deliberate-validate.py scripts/_deliberate_shared.py` (or equivalent) before every invocation.

## Declared bounds

All declared bounds are immutable v1 constants from `references/contract-data.yaml`, including the validator parse caps. The echo and every capsule carry the exact canonical map; an invocation, pasted capsule, echo override, or re-run directive that differs is preflight `invalid invocation` before store creation. `capsule-bytes` governs chat rendering and ordinary capsule ingest. `capsule-file-bytes` is the larger, explicit-only validation and import cap after a chat capsule still cannot fit following full compaction; using it requires `--file-capsule`, and the file capsule keeps the underlying semantic terminal rather than adopting the bound-exceeded receipt's label.

<!-- generated:bounds -->
- `in-packet-evidence-bytes`: 262144
- `directory-expansion-max-descendants`: 512
- `named-evidence-expanded-bytes`: 67108864
- `per-stage-retrievals`: 32
- `verbatim-directive-history`: 8
- `capsule-bytes`: 262144
- `capsule-file-bytes`: 1048576
- `parse-bytes`: 1048576
- `parse-depth`: 32
<!-- /generated:bounds -->

Every bound is mechanically enforced at the operation it protects: in-packet and named-evidence argv aggregates before hashing and complete stored identity-list aggregates when pins and capsules are validated; directory descendants before content reads; retrievals before envelope acceptance; directive history and exact canonical bound equality during capsule validation; ordinary chat and ingest bytes against `capsule-bytes`; explicitly requested file validation and import against `capsule-file-bytes`; parse bytes and depth before object construction. Capsule `bounds` must equal the complete canonical map generated above, never merely an empty, partial, or different fixed-key positive-integer mapping.

## The labeled record key set

Exclusion records (Prune) and disposition records (Recommend) share one key set. Envelopes and the capsule carry the keyed YAML form; chat renders the labeled text template in `references/methods.md`. Prune's cut bases are `constraint`, `equivalence`, `dominance`, `survivor budget`; Recommend's are `post-prune filter`, `post-prune dominance`, `post-prune collapse`, `only-serious-option rival`.

<!-- generated:record-keys -->
- `option` — required. complete original wording, provenance flag intact — validation rejects paraphrase
- `status` — required; one of: active, revived. revived — historized by a revival directive: capsule history only, outside Contest eligibility and every packet
- `delegation` — required. what the invocation authorized here
- `predicate-source` — required; one of: direct user rule, agent-derived proposition
- `cut-basis` — required; one of: constraint, equivalence, dominance, survivor budget, post-prune filter, post-prune dominance, post-prune collapse, only-serious-option rival
- `epistemic-status` — required; one of: fact-established at comparable resolution, contestable sketch-depth judgment
- `reason` — required
- `evidence-provenance` — optional. list of {source, retrieved-at} for each external fact the reason or epistemic status relies on; each must resolve to a stored or same-envelope retrieval
- `load-bearing-premise` — required
- `strongest-case` — required. written before the kill
- `revive-if` — required
- `evidence-warning` — optional
<!-- /generated:record-keys -->

## deliberate-setup/v1

One authored setup document for an initial run. `init-setup` validates it before creating the store, derives the echo and decomposition from it, writes those two items in order, and returns nonzero immediately if either write fails. Candidate-attached language is authored only in an entry's `authority-note`; only its separate candidate-neutral `criteria` values enter `soft-prefs`.

The setup carrier has one load-bearing serialization rule: use a YAML `|-` block scalar for every free-prose value, including initial wording, frame, constraint and price text, stated values, stakes, evidence prose, candidate wordings and attached candidate keys, criteria, authority-note text and span, and both composition-provenance spans. Use plain scalars only for schema names, provenance and mode enums, booleans, numbers, `absent`, and `none`. This is mandatory even when the current text appears colon-free because `init-setup` is the single attempt: a syntax failure stops the run and may not be repaired inline.

```yaml
composition-provenance:
  invocation-span: |-
    Field mode: seed-and-widen; candidate wording elided here.
  delegation-span: |-
    Run the complete deliberation now.
```

Never write `invocation-span: Field mode: seed-and-widen` as a plain scalar; the second colon is YAML syntax, not prose.

<!-- generated:setup-keys -->
- `schema` — required; constant `deliberate-setup/v1`
- `invocation-wording-initial` — required
- `directives` — required. empty on an initial run
- `directives-collapsed` — required. empty on an initial run
- `fields` — required. map of every validation.echo-contract-fields entry except soft-prefs, each {value, provenance}; soft-prefs is derived only from soft-preferences.entries[].criteria
- `candidates` — required. list of {wording, provenance-flag}; authority notes cannot be authored here. Init-setup canonicalization rule: candidate wordings and the soft-preference entries naming them are canonicalized at this ingress (internal whitespace runs collapse to one space, ends trimmed), duplicates are rejected after that normalization, and the stored canonical bytes are the identity every later surface must match exactly
- `soft-preferences` — required. {provenance, entries}; each entry is exactly {candidate, criteria, authority-note}; candidate is `absent` for a neutral preference and requires authority-note `absent`, or one exact candidate wording with its complete candidate-attached language only in authority-note; only candidate-neutral criteria are flattened into echo and decomposition soft-prefs
- `composition-provenance` — required. {invocation-span, delegation-span}, candidate-free by elision
- `bounds` — required. exact canonical top-level bounds map
- `source-capsule-id` — required. `none` on an initial run
<!-- /generated:setup-keys -->

## deliberate-envelope/v1

One fenced YAML document per stage return: UTF-8, fixed key set (unknown keys rejected), prose values as block scalars — transport, never a semantic form the judgment agent fills to feel done.

<!-- generated:envelope-keys -->
- `schema` — required; constant `deliberate-envelope/v1`
- `stage` — required; one of: generate, prune, shape, recommend, contest
- `status` — required. three-class grammar, mechanically enforced: `completed`, `exit: <the named honest exit>`, or `failed: <reason>`
- `artifacts` — required. map carrying exactly the stage's obliged-artifact keys; each value present, `not produced: <reason>` (never on a completed stage), or (conditional artifacts only) `not applicable`
- `retrievals` — required. `none`, or list of {source, retrieved-at, fact, concerns} — concerns is `candidate-neutral` or the list of every candidate the fact names, evidences, or was retrieved to investigate; capped by bounds.per-stage-retrievals
- `encounters` — required. `none`, or a list of mappings; each mapping is exactly {kind: withheld-class | instruction-like, where, note}; scalar string entries are invalid
- `pins` — required. `none`, or a list of mappings; each mapping is exactly {surface, id}, where surface is non-empty and id is a full 64-hex content identifier for a surface the stage actually verified; legacy maps using class, path, verified, or any extra key are invalid
- `model` — required. effective model when observable; `unknown` otherwise
<!-- /generated:envelope-keys -->

## deliberate-runstate/v1

Every orchestrator-written run-state store item; helper-validated at write exactly as envelopes are at acceptance. Item files are named `<seq>-<kind>[-<stage>].yaml` under the store root.

<!-- generated:runstate-keys -->
- `schema` — required; constant `deliberate-runstate/v1`
- `kind` — required; one of: echo, decomposition, pins, envelope, brief-render, terminal-claim, proof-inputs, terminal-state, capsule-progress, capsule-import, restart-plan
- `run` — required. run identifier; every item carries it and must match the echo item's
- `seq` — required. monotonic write sequence integer; the echo item is seq 0 and the store's first write
- `stage` — optional. required for envelope and brief-render items
- `body` — required. keyed payload per kind; fixed top-level key set per body-keys below

Body key sets per kind:

- `echo`: `invocation-wording-initial`, `directives`, `directives-collapsed`, `fields`, `setup-source`, `bounds`, `source-capsule-id`
- `decomposition`: `frame`, `candidates`, `stakes`, `soft-prefs`, `values`, `composition-provenance`
- `pins`: `constituents`, `method`, `evidence`, `in-packet`
- `envelope`: `document`, `amendments`
- `brief-render`: `brief-id`
- `terminal-claim`: `terminal`, `claim`, `survivor`
- `proof-inputs`: `packet-isolation`, `read-isolation`, `constituent-pins`, `method-identity`, `effective-models`, `evidence-scope-used`, `containment`, `store-path`, `collapses`, `not-proven`
- `terminal-state`: `terminal`, `carrier`
- `capsule-progress`: `capsule`
- `capsule-import`: `capsule`
- `restart-plan`: `earliest-stage`, `reasons`, `directives`
<!-- /generated:runstate-keys -->

The echo body's `bounds` equals the exact canonical top-level map in `references/contract-data.yaml`; `source-capsule-id` is `none` for an initial run or a full SHA-256 for an import. Its `setup-source` is the helper-normalized candidate, preference, and composition source from which decomposition is derived exactly. `init-setup` writes echo then decomposition from one `deliberate-setup/v1` input; decomposition is not a generic write kind, and pins cannot be written while decomposition is absent. These are stored authority for capsule comparison, never reconstructed from conversational memory. Store items append at the exact next sequence number; setup and terminal authorities are singletons, each stage has at most one brief render and one envelope, an envelope's outer stage equals its document stage, and envelope acceptance requires that stage's recorded brief. Failed envelopes remain stored diagnostics but never supply effective artifacts, records, retrievals, or downstream progression. The reserved `proof-inputs` item is the byte-exact authority for the capsule proof boundary and is written only by `record-proof-inputs` before terminal acceptance; its `store-path` is the sole normalized member, realpath-compared with the live store root and persisted as that helper-owned canonical root. `terminal-state` requires proof inputs, seals every write except the one capsule-progress acceptance, and accepted capsule progress seals the store completely. Import alone writes `restart-plan`: `earliest-stage` is `none` or one canonical stage, `reasons` is a non-empty classified list, `directives` is the typed manifest binding each new raw directive text to its applied actions (helper-synthesized entries for flag-only imports, empty when nothing textual or flag-derived applied), rendering and acceptance refuse a stage before that frontier, and no later stage may proceed until the frontier has a non-failed envelope; imported stage artifacts at or after the frontier remain unavailable until replaced.

## deliberate-capsule/v1

The recovery capsule (and, with `not produced` markers and a recorded failure terminal, the failure capsule). Every key is present on every capsule; `capsule-complete` is the final key, carrying a content identifier over every byte of the document strictly before the line on which it appears — a terminator-less or identifier-mismatched paste fails validation as incomplete. The chat-rendered capsule and ordinary ingest are bounded by `capsule-bytes`; only an explicitly requested file capsule may use `capsule-file-bytes`, via `--file-capsule`, while retaining the underlying terminal.

<!-- generated:capsule-keys -->
- `schema` — required; constant `deliberate-capsule/v1`
- `run` — required
- `terminal` — required. the non-empty terminal from the store's reserved terminal-state item, normally `close rendered` when Recommend's close stands; every capsule terminal must match one canonical validation.capsule-terminal-classes entry, a failure terminal, or the `constituent exit at <stage>: <named exit>` form over validation.constituent-exit-stages — an unmatched terminal is refused, and artifacts at or after the class frontier must not be produced; receipt-only and echo-only terminals refuse capsule validation; `store failed: write` alone may lack terminal-state under its failed-write exception
- `effective-contract` — required. map: frame, field-mode, constraints, values, soft-prefs, stakes, evidence-inputs, evidence-authorization, evidence-identity, method-identity, survivor-budget, degradation-permission, bounds, invocation-wording: {initial, directives (newest verbatim texts within bounds.verbatim-directive-history), directives-collapsed (older directive texts as content identifiers, oldest first), source-capsule-id}; fields named by validation.echo-contract-fields each carry {value, provenance}; every named and in-packet evidence identity entry carries its measured bytes for aggregate re-summing and method-identity carries exactly validation.method-surfaces, except an echo-only `store failed: write` capsule uses `not produced: pins not written` for both pin-derived members; bounds equals the exact canonical top-level bounds map
- `setup-decomposition` — required. map: frame, candidates (each {wording, provenance-flag, authority-note}), stakes, soft-preferences ({provenance, entries} in the normalized setup-source shape), composition-provenance ({invocation-span, delegation-span}); validation re-derives candidates and effective-contract soft-prefs from this source so a pasted capsule cannot relabel candidate-attached language as neutral
- `field-order-origin` — required. `user-supplied` | `generate-produced` when original-field exists; `not produced: <reason>` iff original-field is absent. Latest validated Generate fixes `generate-produced`; otherwise import preserves the prior value; an initial or newly supplied closed field fixes `user-supplied`; prior-full-field adoption preserves `generate-produced`.
- `recommend-authority-packet` — required. survivor wordings; order-provenance exactly the label derived from field-order-origin via validation.order-origin-labels; per-option insertion provenance when applicable; per-survivor authority notes; any overflow disclosure; stakes/reversibility
- `original-field` — required. complete generated or user-supplied field — present whenever any field was validated; `not produced: <reason>` only on a failure before Generate returned a validated field
- `generation-boundary` — required. untouched-fixed-points line | `Generate not run: closed-to-widening` | not produced; prior-full-field adoption preserves the imported fixed-points boundary, while the not-run marker belongs only to an initial, newly supplied, or prior-seeds-only closed field
- `survivors` — required
- `overflow` — required. any disclosed budget overflow with its blocked-cut disclosures
- `records` — required. every exclusion and disposition record with its `status`
- `retrievals` — required. the run's accepted retrievals in full — each with producing stage, source, retrieval time, and effective `concerns`
- `surface` — required. Shape's comparison surface, verbatim when produced
- `consequences` — required. Shape-recorded constraint consequences
- `close` — required. Recommend's close, verbatim when produced
- `registered-leans` — required. Recommend's registered leans ({agent-first-lean, user-visible-lean}), verbatim when produced
- `terminal-claim` — required. the close-less terminal's claim item ({terminal, claim, survivor}); required whenever active records make Contest eligible and close is not produced, with survivor required on the one-survivor branch; otherwise `not produced`
- `exclusion-check` — required. the rendered exclusion check line
- `provisional-seed` — required. exact `not applicable` when Recommend completed without a seed; `not produced: <reason>` only when Recommend is absent or invalidated; otherwise an unaccepted {wording, handle, core-idea, distinct-bet}, every value a non-empty string; acceptance has no free-form wording argument
- `revival-instructions` — required
- `proof-boundary` — required. map: packet-isolation, read-isolation, constituent-pins, method-identity, effective-models, evidence-scope-used, containment, store-path, collapses, not-proven; an echo-only `store failed: write` capsule uses `not produced: pins not written` for the two pin-derived members
- `capsule-complete` — required. final key; content identifier over the document body above it
<!-- /generated:capsule-keys -->

### Nested and cross-field validation

The helper validates this as a typed recovery state, not a top-level inventory. Duplicate YAML keys at any depth fail before construction; every map has a fixed key set; required prose and identifiers are non-empty strings of their declared shape; enum values come from `contract-data.yaml`'s `validation` section; and lists contain only typed members, with duplicate candidate wordings and duplicate active records rejected. The setup decomposition carries the normalized `soft-preferences` source; capsule validation re-derives its candidate authority notes and effective-contract `soft-prefs`, rejecting a missing source, a mismatched note, or candidate-attached wording relabeled as a neutral criterion.

`field-order-origin` is independent of current field mode. A real Generate boundary requires `generate-produced`; `Generate not run: closed-to-widening` requires `user-supplied` and belongs only to an initial, newly supplied, or prior-seeds-only closed field. Prior-full-field adoption preserves both the imported fixed-points boundary and `generate-produced` origin, so changing mode never launders Generate order into user order. The Recommend packet's rendered order-provenance is derived from this field and must equal its canonical label. A revived option rejoining a reused field carries `insertion: original-field-position`; a canonically accepted seed appended to that field carries `insertion: appended-by-rule`; a fresh Generate output and prior-full-field adoption have no insertion event. Prune preserves each option object, including insertion, byte-exact while taking an order-preserving subsequence.

The terminal/artifact state is validated as one **total** state machine over the canonical terminal classes. Every non-failure capsule terminal must match one `validation.capsule-terminal-classes` entry or the `constituent exit at <stage>: <named exit>` form (stages from `validation.constituent-exit-stages`; an exit at Generate is echo-only and refused); a terminal matching nothing is refused as free-form authority, at `record-terminal` and at capsule validation alike. Each class fixes an artifact frontier — artifacts of stages at or after it must be `not produced` — so a completed run can never be relabeled as an earlier honest exit while retaining downstream artifacts. `record-terminal` writes the reserved `terminal-state` item with carrier `capsule` or `failure-capsule`; receipt-only and echo-only terminal classes refuse capsule validation. `store failed: write` is the only allowed capsule terminal without a newly written terminal-state item. A close-less Contest-eligible state with active records requires a stored terminal claim before Contest rendering or capsule acceptance; if Contest fails, the underlying terminal and claim remain unchanged while only `exclusion-check` becomes `exclusion check unavailable`. A close-rendered state requires the stored close, and a Recommend constituent exit (`options not comparable`, `no basis yet`, `only one serious option`) carries its exit statement as the close. A failure capsule may expose only artifacts from stages accepted before the failed stage; values returned inside the failed stage's envelope are diagnostic only, never recovery authority, and that stage's artifacts are `not produced: <reason>`. Field absence propagates to every downstream artifact; active records form an exact, duplicate-free partition against the stored field and survivors; and receipt-only terminals can never be relabeled capsules.

Terminal-time validation is store-backed: `record-proof-inputs` first realpath-compares the submitted store locator with the live root, persists the canonical root in the otherwise byte-exact proof-boundary body, and returns before any separate `record-terminal` call may run. A nonzero proof result forbids terminal recording. Then `validate-capsule --store <store> --accept` compares every store-derived capsule value, including terminal state, field/order origin, records, retrievals, close, exclusion check, and the complete proof boundary, and writes the reserved `capsule-progress` item. Import uses full typed validation without a prior store. `store failed: write` is the narrow circularity exception: it still requires `validate-capsule --store`, but cannot require `--accept`, a newly written proof-inputs item, or a newly written terminal-state item from the failed write path. If decomposition was not durable, store comparison re-derives it from the echo's setup source; if pins were not durable, all four pin-derived capsule members must be `not produced: pins not written`, and any substituted identity fails.

## Validator exit codes

`0` pass · `1` validation failure · `2` refusal (unauthorized read, off-column request, unsupported schema, bound breach, usage) · `4` required run-state item absent — the orchestrator maps exit 4 to `store failed: read`, and exit 2 on a pasted capsule's schema version to the preflight refusal (a capsule under an unsupported schema resumes only through a shipped migration, never reinterpreted).

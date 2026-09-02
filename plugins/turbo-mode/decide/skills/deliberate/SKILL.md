---
name: deliberate
description: "Run one complete autonomous deliberation: generate options, prune on a contestable ledger, shape survivors, recommend honestly, contest the exclusions. Returns a close plus a re-run capsule. To develop one approved design collaboratively, use `design-exploration` instead; when serious, comparable options already exist and you only want the choice, use `making-recommendations` directly. Give the decision frame; optionally candidates with field mode, constraints at price, values, evidence with its authorization, and a survivor budget — or paste a prior capsule with directives."
disable-model-invocation: true
argument-hint: "[decision frame; candidates + field mode?; constraints at price?; values?; evidence + authorization?; survivor budget?; or: pasted capsule + re-run directives]"
---

# Deliberate

One explicit invocation (`/deliberate` or `$deliberate`) runs **Generate → Prune → Shape → Recommend → Contest** in packet-isolated stages and returns a close plus a recovery capsule. It asks no mid-run decision question; host permission prompts are outside this promise. **Complete every judgment the run can honestly own, never manufacture a winner.** All four `making-recommendations` close shapes are successful completions.

## Mandatory reloads

This spine is intentionally incomplete without its references. Before setup and preflight, read `references/schemas.md`, `references/stage-packets.md`, and `references/capsule.md`. Re-read `references/stage-packets.md` before **every** stage dispatch; also re-read `references/methods.md` before Prune and Contest, and the live constituent contract before Generate, Shape, and Recommend. Re-read `references/capsule.md` before every terminal, capsule construction, and re-run preflight. These reads are mandatory even when the files were read earlier in the run.

`references/contract-data.yaml` is canonical for the matrix, brief template, schemas, validation data, terminals, and writer ownership; it wins over authored renderings. `scripts/deliberate-validate.py` loads it for all mechanical operations. Orchestrator judgment never replaces the helper.

After compaction, re-derive the fixed store locator, verify its echo, and rebuild exact packets and capsules from the store under freshly read references. Never use summarized memory for a compared value. No capsule is displayable until store-backed validation accepts it.

## Invocation contract and echo

The invocation carries the following fields; `references/capsule.md` owns their re-run transitions and `references/schemas.md` owns their bounds and shapes.

- **Decision frame** — mandatory; indiscernible → ask once before the run starts (pre-run, not mid-run).
- **Field mode** — `seed-and-widen` by default, or `closed-to-widening`, which skips Generate; candidates require an explicit or echoed mode, and a closed echo says Prune may still narrow the field.
- **Confirmed constraints**, each at its price. Unconfirmed constraints demote to soft preferences that never gate alone.
- **Stated values**, **soft preferences**, and **stakes context** (optional) — values are pre-answered exchange rates; soft preferences are context, never gates; absent stakes stay absent and Recommend reads the door.
- **Evidence inputs** kept separate from **evidence authorization**. Supplied inputs and named paths may be inspected by default; additional sources, web research, and probes require echoed authorization. Only read-only inspection, research, and explicitly non-mutating probes can be authorized; side-effecting checks return as `check first`.
- **Survivor budget** — default 4; a provisional capacity budget, explicitly not a claim about correct comparison width.
- **Inline-degradation permission** (optional) — covers isolation only, never mechanical validation.
- **Re-run payload** (optional): a pasted prior capsule plus directives — directive-free only when the capsule records an unfinished run.

The contract echo labels every material field `user-supplied`, `inferred`, `default`, or `absent`. Visible setup, correctable by live interruption where the session supports it, otherwise by re-run — no universal interrupt promise. Every re-run echo also surfaces each active record-cited retrieval with its source and retrieval time (excluded-fact freshness is user-owned by disclosure).

Declared bounds are immutable v1 constants from `references/contract-data.yaml`. Every echo and capsule must carry that exact canonical map; an invocation, pasted capsule, echo override, or re-run directive that differs is `invalid invocation` before store creation.

Apply every preflight refusal and normalization rule in the mandatory references. Reject with `invalid invocation: <reason>` and echo only any invalid field mode or budget, invalid or unsupported capsule, missing directives for a completed capsule, unclassifiable directive, bound breach, or pasted emergency receipt. An unfinished capsule is an implicit resume request. Invocation from a detectable cron job, hook, scheduled task, or another skill exits `unsupported invocation context`.

Before spending, verify the helper — the entrypoint and every imported production module — with `shasum -a 256` and run its fixtures if untested this session. A helper that cannot verify or execute is `capability unavailable`; missing fresh-agent isolation is the same exit unless inline degradation was authorized. Create the run-state store only after all other preflight checks pass; failure before its first durable write is `store unavailable`.

Setup has one authored source: a `deliberate-setup/v1` document carrying every echo field except derived `soft-prefs`, the candidate set without authority notes, and normalized soft-preference entries. A neutral entry uses `candidate: absent`, an `authority-note` of `absent`, and one or more candidate-free `criteria`; a candidate-attached entry names one exact candidate, carries the complete attached language only in its span-grounded `authority-note`, and carries only separable candidate-neutral `criteria` (possibly none). Ambiguity becomes `absent`, never invented lean. The setup carrier uses YAML `|-` block scalars for every free-prose value — initial wording, frame, constraints and prices, values, stakes, evidence prose, candidate wordings and attached candidate keys, criteria, authority-note text and span, and both composition-provenance spans — even when a value currently appears colon-free; schema names, provenance enums, booleans, numbers, `absent`, and `none` stay typed scalars. In particular, never emit a plain scalar such as `invocation-span: Field mode: seed-and-widen`; the first colon-bearing phrase would make the one allowed setup attempt unparsable. `init-setup` derives both echo and decomposition from that source and writes them in order; never author or write either artifact separately. It canonicalizes candidate wordings and the soft-preference entries naming them — whitespace runs, newlines included, collapse to one space — and rejects post-normalization duplicates; the stored canonical bytes are the identity every later surface compares against exactly, so a block-scalar soft-wrap in an authored candidate never survives into wording identity. If `init-setup` returns nonzero, stop setup immediately — do not attempt pins or any later helper call. The store independently refuses pins until decomposition exists. Display the derived echo and decomposition, then pin the full constituent set, evidence and manifests, in-packet bytes, and method identity. Mandatory references own the shapes and read set.

## The authority model

> The invocation delegates stage transitions and field changes under the echo. It does not authorize invented constraints or value weights, evidence beyond scope, side effects, or silent collision resolution. Missing authority survives into an honest exit or close.

Only supplied or directly evidenced confirmations become price-confirmed constraints; inferred constraints and values stay soft. The ledger separates **permission to decide from authorship**: equivalence, dominance, and predicate satisfaction remain agent judgments and are recorded as such.

## Run shape

Five moves, all five packet-isolated in fresh, non-forked stage agents — Contest included, mandatory on every Contest-eligible branch. Stages receive ambient instructions and can read the filesystem; "blind" is not claimed. The isolation rule throughout: **hide previous-stage judgments, never decision-controlling user authority.**

1. **Generate** executes live `ideate`, returning an un-ranked field and untouched-fixed-points line; supplied seeds are collapse-exempt.
2. **Prune** executes the deliberate-owned method: decisive cuts without scores or invented weights, returning an order-preserving survivor subsequence, complete exclusion records, and any disclosed budget overflow.
3. **Shape** executes live `option-shaping` on frozen survivors under the authorized-composition seam; it records confirmed-constraint consequences without cutting and exits on identity-blocking collision.
4. **Recommend** executes live `making-recommendations` on the comparison surface and complete authority packet; it owns filters, honest exits, and a disposition record for every new exclusion.
5. **Contest** executes the deliberate-owned detection-only method against the close or close-less `terminal-claim`; a visible user preference on an excluded candidate is always a live challenge.

**Orchestrator obligations, every stage:**

- Apply the dedicated fail-fast helper-call boundary from `references/stage-packets.md` to every store mutation. A nonzero helper result prevents every later store-mutating helper on that branch; receipt rendering and cleanup never reopen the store write sequence.
- Render every complete matrix brief from stored values with `render-brief`, record its identifier, and dispatch its bytes unaltered. Never hand-assemble or override an off-column refusal. Store the canonical `terminal-claim` before a close-less eligible Contest render.
- Accept only `validate-envelope --accept` output. A validated `failed: pin mismatch — constituent:<path>` becomes `constituent drift`; `evidence:<path>` becomes `evidence drift`; `method:<path>` becomes `method drift`. Every other failed envelope, timeout, or malformed packet is `stage failed: <stage>`.
- Verify constituent, evidence, and method pins before every stage and before each owned-reference or helper use; verify the validator and its imported production modules with the platform hasher. A drifted validator or module takes the emergency-receipt branch.
- In a Git worktree, compare net Git-visible state before and after every stage. Unauthorized mutation is `containment violation`: stop with a dirty-state receipt, never restore or adopt silently. This proves only net Git-visible change.
- Preserve the session model where supported. Record each effective model at its provenance: a value not drawn from introspected ground truth is `self-reported: <value>` or `unknown`, never bare fact, and disagreeing ambient sources are recorded as the disagreement, never resolved by picking one. Report transitions and counts without hidden judgments.

**Global exit rule:** any constituent honest exit not explicitly transformed by this contract terminates the run as that exit; the orchestrator names the next lane, never asks a mid-run permission question, never silently enters that lane, and records the terminal canonically as `constituent exit at <stage>: <the named exit>` — capsule-bearing only at Shape and Recommend; an exit at Generate is echo-only. Muddy goal at Generate → `outcome-shaping`, echo only.

**Operational failure rule:** a typed failure capsule preserves only validated artifacts and restarts at the earliest invalid one. Helper or store-read failure gets a non-resumable receipt. If Contest fails, the underlying semantic terminal and pre-Contest claim stand while `exclusion-check` becomes `exclusion check unavailable`; no exclusion-stability claim is made. Store terminals are `store unavailable`, `store failed: write`, and `store failed: read` as defined in the capsule reference.

## Composition seams

Only seams rendered from `contract-data.yaml` bind: questions and handoffs become packet-contained gaps or exits; Generate protects seeds; Shape receives evidenced composition provenance and freezes the field; Recommend registers leans before surface and consequences, stays within evidence authority, adds no unshaped comparison candidate, and records every exclusion. Otherwise obey the live constituent; uncovered conflict becomes its honest exit.

## Close

After reloading the capsule reference, follow its total branch table and close order: **exclusion check → recommendation or honest exit → one terminated `deliberate-capsule/v1` document**. Emit only existing artifacts. For a capsule-bearing terminal, assemble and compact enough to fix the carrier, record proof inputs and terminal state in separate fail-fast helper calls, then run `validate-capsule --store --accept` in its own call; the proof recorder realpath-compares the submitted store locator with the live store and persists the helper-owned canonical root. The first nonzero helper result ends all later helper invocations for that run, including a corrected or diagnostic second validation probe; only contract-selected receipt rendering and cleanup may follow without invoking the helper. Receipt/echo-only terminals refuse validation, while `store failed: write` still requires comparison without a new write. The final content field is the recorded proof boundary. If chat compaction still cannot meet `capsule-bytes`, emit the non-resumable bound receipt and wait; an explicitly requested file capsule keeps the underlying semantic terminal and validates under `capsule-file-bytes`. `trash` the store only after the recovery carrier exists; disclose retirement failure.

## Re-runs

Restart at the earliest invalid input or artifact under `references/capsule.md`. `import-capsule` validates typed restart state and writes a reserved restart plan; only imported stage artifacts before its earliest-stage frontier remain available, stage artifacts at or after it stay unavailable until a new accepted envelope supplies them, and no envelope is synthesized. Re-resolve identities live, supply the current pins to import, and pass any additional classified source-drift frontier explicitly. New directive texts enter with a typed manifest binding each text to its applied actions — orphan text and orphan actions refuse before the store is staged. Revival marks provenance and rejoins at its original position in a reused field; no-argument `--accept-seed` accepts only canonical stored wording. A field-mode change supplies its explicit base when landing closed. Preserve field-order origin and transition insertion provenance. Prior judgments enter only named packets.

## Helper

```bash
V=scripts/deliberate-validate.py; M=scripts/_deliberate_shared.py; D=references/contract-data.yaml   # paths relative to this skill directory
shasum -a 256 $V $M
uv run --script $V fixtures --data $D
uv run --script $V identity --data $D [--as-evidence | --as-in-packet] <path>...
```

The store-mutating forms are `init-setup`, `write-item`, `render-brief`, `validate-envelope --accept`, `record-proof-inputs`, `record-terminal`, `validate-capsule --accept`, and `import-capsule`. Run exactly one in each shell or tool call, beginning that call with `set -euo pipefail`; never paste a mutation sequence as one script. Inspect every helper result before invoking the helper again, and after the first nonzero result do not invoke any helper command again during that run, including non-mutating validation. Use command `--help` and the mandatory references for complete syntax, including dedicated setup initialization, the remaining store writes, and storeless ingest validation. The store root is the fixed `deliberate-run-live/` directly under the runtime's ambient session-scoped temporary root. No detectable root → `store unavailable`. Exit codes: 0 pass, 1 validation failure, 2 refusal, 4 store read loss.

## v1 boundaries

Read-only toward user-visible state throughout; no auto-revival loop; no persistence beyond the run by default (the store is retired to the user's local Trash at close — no live store survives the run, and byte destruction is never claimed); chat-first — the capsule is written to a file only on request; never fired from cron, hooks, or another skill.

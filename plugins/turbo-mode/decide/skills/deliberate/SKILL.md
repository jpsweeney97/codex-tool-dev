---
name: deliberate
description: "Use when the user wants one decision deliberated end to end without steering each step: widen the options, cut the field with recorded reasons, develop the survivors, recommend honestly, then check the cuts against the recommendation — 'think this whole decision through for me', 'run a full deliberation on X'. Not for picking among options that are already comparable (`making-recommendations`), one phase steered by hand (`ideate`, `option-shaping`), a still-muddy goal (`outcome-shaping`), or settling a design (`design-exploration`)."
argument-hint: "[the decision, in a sentence or a file; optionally your candidates, hard constraints, and your lean]"
---

# Deliberate

Run the decide plugin's forward chain on one decision in five stages without stopping to ask: **Generate → Prune → Shape → Recommend → Contest**. The user gets a recommendation in `making-recommendations`' own close, a ledger of every option that was cut and why, and a one-line check of those cuts against the recommendation's reasoning. Invocation: `/deliberate` or `$deliberate`, or a plain request for the whole run.

The principle that governs every stage: **complete every judgment the run can honestly own, and never manufacture a winner.** All four `making-recommendations` close shapes (clear call, conditional call, check first, your call) are successful completions.

## What the user brings

A decision question, in a sentence or a file. Optionally: candidates they already have, constraints they are sure of, what they value, files to read, and their current lean. Everything absent defaults: the field is widened even when candidates are given, about four survivors are kept, and evidence is what the user supplied plus what is already in the working context.

Plain-language steering the run honors: "don't add options" skips Generate and starts at Prune; "keep six" changes the survivor count; "you may research" allows web lookups in every stage; a model name ("use Sonnet for the stages") sets the stage model.

If the decision question cannot be stated from what the user gave, ask one question before the run starts. If the goal itself is muddy, name `outcome-shaping` instead of running. Once the run starts it asks nothing; host permission prompts are outside that promise.

## Setup, shown before the first dispatch

Create a fresh run directory under the runtime's scratch or temp root (Claude Code's scratchpad; `mktemp -d` elsewhere) and write `00-setup.md` with: the decision question; the user's candidates, marked as theirs; each hard constraint the user confirmed, with what it costs; stated values; the evidence stages may read and whether research is allowed; the survivor count; the model the stages will run on; and the user's visible lean, if any. Mark anything inferred rather than told `inferred`.

Show the setup to the user in a few lines and start the run in the same turn. The user can interrupt to correct it; the run does not wait. Between stages, give one line naming the stage starting and what it received as counts, not content.

## The five stages

Each stage runs as a fresh agent with its own context, dispatched with a brief the orchestrator composes from `00-setup.md` and the previous stage's output file. On Claude Code, pass `model: opus` on every stage dispatch unless the user names a model; on another runtime, use its subagent model setting. Opus is the default because a run is five long dispatches. The fresh context is what keeps the user's lean, and each stage's reasoning, out of the stages that must not see them. Where the runtime cannot dispatch a fresh agent, run the stages in this context in order, still writing every file, and say in the close that the stages were not isolated.

Every brief tells the stage agent: which sibling skill to read and follow (`../ideate/SKILL.md`, `../option-shaping/SKILL.md`, or `../making-recommendations/SKILL.md`, next to this skill's directory) or carries the method text below; to quote option wordings exactly as given; to change nothing outside its own output file; and to write its result to the named file, which overrides the sibling skill's chat-first default, then reply with two lines. The orchestrator reads the file, not the reply, before composing the next brief.

| Stage → file | Runs | Brief contains | Brief withholds |
| --- | --- | --- | --- |
| Generate → `01-field.md` | `ideate` | question, constraints, values, evidence; the user's candidates as seeds to keep as written | the lean |
| Prune → `02-prune.md` | the Prune method below | the field with the user's candidates marked; question, constraints at their price, values, survivor count | the lean; Generate's reasoning |
| Shape → `03-shaped.md` | `option-shaping` | the survivors in field order, exact wordings; question, constraints, values, evidence; a statement that the user invoked `deliberate` and delegated candidate selection to the run | the lean; the cut records |
| Recommend → `04-close.md` | `making-recommendations` | the shaped comparison surface; question, constraints, values, evidence; the user's visible lean, named as such; an instruction to append a cut record (shape below) for any survivor it sets aside by filter or dominance, and to name as added any option it adds | the cut records from Prune; Prune's and Shape's reasoning |
| Contest → `05-contest.md` | the Contest method below | the close, every cut record from Prune and Recommend, the shaped surface, the setup including the lean | nothing further |

Recommend receives the lean because its own contract registers the user's lean and attacks it. The earlier stages do not, because a stage that knows the favorite widens, cuts, and develops toward it.

`Recommend` follows the live `making-recommendations` contract, which may add an option to the shaped field. Its brief tells it to name each addition as added in `04-close.md`. Contest decides whether an added option is substantively the same as a Prune cut and, when it is, names that cut as a live challenge in the existing one-line form.

If a stage returns one of its sibling skill's honest exits or handoffs instead of its artifact (`ideate` handing to `outcome-shaping`; `option-shaping` returning `field collision unresolved`; `making-recommendations` exiting `options not comparable` or `no basis yet`, or handing to another skill), the run ends there as that exit. Report it, name the skill it points to, and stop. Do not enter that skill and do not ask a mid-run question.

## Prune

You narrow the field decisively, with a recorded reason for every cut, and never with scores or invented weights. You do not know which candidate the user favors; your cuts must be defensible without knowing.

Cuts you may make regardless of the survivor count:

- An option fails a confirmed hard constraint. Say which constraint and how.
- Two options would succeed or fail for the same reason. Name that reason and keep one; when one of the pair is the user's candidate, keep the user's wording and cut the generated one.
- One option is at least as good as another on everything that matters and better on something, at the depth you can actually see.

Cuts to reach the survivor count come after those. Each is a low-confidence cut of a candidate whose seriousness you could not resolve at sketch depth; say exactly that in the record, never that the option was "not serious". If you cannot reach the count without deciding a trade between the user's values that they have not priced, do not invent the weight: keep the extra survivors, say which trade blocked the cut, and carry them forward. If that leaves more than about twice the count, the run ends with `survivor count cannot be met without an unstated value trade`, and the records are the output.

Rules that hold throughout: keep survivors in field order; never cut below two unless confirmed constraints leave fewer, and if they leave none the run ends with `no option survives the confirmed constraints`; a candidate the user supplied dies only by a recorded cut, never by collapse or omission.

Write `02-prune.md` as the survivor list in exact wordings, then one record per cut. Label a cut `fact-established` only when its stated reason settles it without interpretation and only a changed constraint or a new fact could revive it; when your `Revive if` names a different reading of the same facts, including one you say you cannot make, the cut is `judgment call`.

```text
Option:         <exact original wording>
Cut:            <constraint | same reason | dominated | survivor count>, <fact-established | judgment call>
Reason:
Strongest case: <for keeping it, written before the cut>
Revive if:
```

## Contest

You test the run's cuts against the recommendation's actual reasoning. Detection only: you identify, and never adjudicate, revive, or recommend.

Find every recorded cut the close makes live: a cut whose reason the close also leans on; a `Revive if` condition the close's own reasoning satisfies or nearly satisfies; a cut whose reason the comparison surface undermines. An excluded option the user visibly preferred is always a live challenge. A cut remains live when the close adopts the option's substance under another wording: the challenge is to the recorded cut, not to the recommendation, so name the cut in the existing positive form. Contest decides whether the added option and cut option are substantively the same; a merely related alternative is not the same option. If the close names only one serious option, test whether any cut's reason being wrong would restore a rival. Never hold an excluded option's lack of development against it; it was never developed, and depth asymmetry is not evidence. When any live challenge exists, name the one most worth contesting.

Write `05-contest.md` as exactly one line:

- `Exclusion check: no live recorded challenge found`
- `Exclusion check: live recorded challenges — <X, Y>; most worth contesting: <one>`
- `Exclusion check: not applicable — no cuts recorded`

## Close

Write `06-close.md` in the run directory, in this order: the Recommend stage's close, as written; the cut ledger as a compact table (option, cut, revive if); the exclusion-check line. In the chat, give the call in one or two sentences, the runner-up and what would flip the call in a few lines, the exclusion-check line as written, the path of `06-close.md`, and one line: "To re-run, tell me which cut to revive, which constraint to change, or which survivor to develop further, and I will restart from the stage that changes." A re-run edits the affected file and runs the stages after it; the earlier files stand.

Say plainly, in the chat, what the run did not do: it did not verify facts the stages marked as assumptions, and it did not develop the excluded options.

## Boundaries

Read-only toward user-visible state: stage agents write only their own output file, and nothing under the working tree changes. If context is compacted mid-run, the files are the record; re-read them rather than reconstruct from memory. Not for cron, hooks, or another skill's dispatch: the run is long and needs a human who will read the close.

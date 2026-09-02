---
name: stage-prompt
description: "Use when the user wants a durable commission prompt to paste into a fresh session elsewhere and have executed there — `stage the commission`, `save that as a commission`, `a prompt I can paste into a session in X` — including commission content already drafted in this chat. Writes a dated, self-contained prompt into `~/prompts` and commits it. Do not use when a reply comes back here for adjudication (`courier` owns the round trip), for same-repo resume context (`save-handoff`), or for tracker publication (`to-prd` / `to-issues`)."
---

# Stage Prompt

A session in one repo works out what needs doing in another, and the user carries it across by hand: fresh session, different rules, nothing shared. This skill writes the commission down so the trip survives it — a self-contained prompt file in `~/prompts`, named so it can be found and committed so it cannot be lost.

Invocation: `/stage-prompt` or `$stage-prompt`, or a plain ask to stage, save, or write up a commission. It also runs retroactively: when this conversation has already drafted the commission in chat, staging it means landing that text as a file, not composing it a second time from nothing.

## One-way, not a round trip

This is the lane where the prompt leaves and does not come back. The consuming session executes the commission under its own repo's rules; nothing returns here for adjudication, and this session's job ends when the file is committed.

When a reply does come back — the user carries something out, another model answers, and that answer lands in this conversation to be verified — the whole relay belongs to `courier`. The tell is the destination, not the wording, because both lanes answer to "a prompt I can paste": ask what happens after the paste. Work gets built there, so stage it. An answer comes back here, so courier it.

## Where it lands

The single home is `~/prompts`: staged commissions at the root, consumed ones in `archive/`. Nothing else — no status headers, no metadata sidecars, no inbox state. The repo is maintained by this convention rather than by machinery, so it carries only as much structure as the convention can bear.

Name the file `YYYY-MM-DD-<target>-<purpose>-prompt.md`:

- **date** — the day it is staged. Use the real current date; never estimate it.
- **target** — a short slug for the repo or area it gets pasted into: `agents` for `~/.agents`, `career` for `~/career`.
- **purpose** — the subject of the commission, hyphenated. Name the thing, not the action taken on it: `stage-prompt-bootstrap`, `design-exploration-methodology-critique`.

If `~/prompts` is absent, it is far more likely un-cloned than new: clone it from the user's remote rather than initializing a fresh one, because a `git init` beside an existing remote builds a divergent history the push cannot reconcile. Initialize only when there is genuinely no remote to clone — `git init`, an `archive/` directory, and a README pointing back to this skill as the owner of the format — and leave adding a remote to the user.

## Self-containment is the hard rule

The consuming session has **zero context** from this one: no memory of this conversation, no knowledge of what was settled here, no way to ask a follow-up question. Everything it needs travels in the file.

Before writing, read the draft back as if you were that session, with this conversation gone. Every path absolute or repo-rooted, every skill and file named in full, every decision that was settled here stated as settled. Nothing session-relative survives that read — no "the file we discussed", no "as above", no placeholder left for someone to fill in. A dead reference is not discovered until the user has already opened the fresh session and spent the trip.

Cite nothing you did not verify. Counts, commit hashes, paths, dates, and prior-art pointers go in only when they are real and checked; where the evidence is thin, say so plainly instead of reaching for a number that reads well. An invented citation is worse than a missing one, because the consuming session will act on it.

## What the commission carries

Open the file with a header line, a separator, then the commission body:

```markdown
# Commission: <subject> — <one clause on what it does>

Paste this into a fresh session rooted in `<target path>`. Self-contained; no other session's context is needed.

---

<body>
```

The body carries as much of what follows as the commission actually has. This is what a commission owes, not a form to fill: a section padded out to look complete spends the consuming session's attention on nothing.

- **Objective** — what to build or do, in the first breath, so the far session knows its job on one read. Open with an effort directive (`ultrathink`, `ultracode`) when the work warrants it.
- **Evidence base** — why the work is wanted, with real counts, dates, paths, and commits where they exist. When there is no evidence base, say what makes the work worth doing instead of manufacturing one.
- **Design requirements** — numbered, each naming the requirement and the failure it prevents.
- **Open questions** — what the consuming session must settle for itself, with your lean where you hold one. Name the decisions that are already made and not up for re-litigation.
- **Target-repo obligations** — the gates the far session will be bound by and should not have to discover mid-run: a charter consult, a validation ladder, a publish path, a delivery mechanism.
- **Reference drafts** — verbatim in fenced blocks, labelled as drafts to re-derive from rather than text to paste.

## Commit

Write the file, then commit it **in `~/prompts`** — not in the repo this session is working in. Stage only the prompt file; message `stage <purpose> commission for <target>`.

Commit on the prompts repo's own default branch. It is a flat single-branch store, and the protected-branch floors that govern working repos are theirs, not this one's: do not import a branch-first rule here and refuse the commit.

Then push it. The remote is private and exists as backup, so pushing here is not publishing — and a commit that never leaves the machine is exactly as lost as one never made. Push fast-forward only: never `--force`, never `--force-with-lease`. A rejected push is a hard stop, not something to reconcile — do not fetch, pull, rebase, or retry. Report the rejection, say the prompt is committed locally and unpushed, and hand the reconciliation back.

## Archive

Only when the user says a commission was consumed: `git mv` it into `archive/`, commit with `archive <purpose> commission`, and push under the same rules as above.

Never infer consumption, scan for it, or check on it unprompted. Sessions in other repos owe this repo nothing — no callback, no status write-back — and that absence is what keeps the convention cheap enough to hold.

## What this is not

- Not a handoff. Resume context for a later session in *this* repo is `save-handoff`.
- Not a tracker artifact. A PRD or sliced implementation issues belong on a publication surface — `to-prd`, `to-issues`.
- Not execution. This skill does not run the commission, open the target session, or arrange the trip. The human is the transport, deliberately.

## Output

```markdown
Staged: <absolute path>
Target: <where it gets pasted>
Committed: <hash and subject | none — why>
```

---
name: relay-by-reference
description: "Use when the user hand-carries a multi-leg exchange between two sessions that share this filesystem — a run session and an adjudication seat, a directing session and a worker — or pastes a relay pointer line, or says `relay this`. Stages each leg as a sha-stamped packet file so only a pointer travels and the body never enters a chat. Do not use when the far side cannot read this filesystem (`courier` composes the paste packet), for a one-way durable commission (`stage-prompt`), or for same-repo resume context (`save-handoff`)."
---

# Relay by Reference

Two sessions, one filesystem, and a human carrying bytes between them: a run session produces a checkpoint, an adjudication seat rules on it, the ruling goes back — sometimes thirteen legs in a single run. Carried by clipboard, those legs truncate mid-sentence, drift under hand transcription, get resent twice four minutes apart, and burn both sessions' context until one dies mid-emission. The two sessions share a disk. Stop shipping bodies; ship pointers.

**Every leg is a file with a sha-stamped header, and the user carries one line.**

Invocation: `/relay-by-reference` or `$relay-by-reference`, a plain `relay this`, or a pointer line pasted in from the other seat.

## What this owns

Transport, not payload. This skill decides how a body crosses the gap and proves it arrived intact; what goes *in* the body belongs to whichever lane is doing the work — a review, a ruling, a commission, a checkpoint.

That is the cut against `courier`, which owns the round trip where the far side cannot read this disk. There the payload has to ride in the user's clipboard, so courier's whole discipline is composing text self-contained enough to survive the trip and adjudicating what comes back. When the far side *can* read this disk, the payload does not have to ride anywhere. The two compose rather than compete: courier can compose a leg that this skill then stages, and a packet whose body is an outside counterpart's claims is still courier's to adjudicate once it verifies.

Neither owns the one-way case. A commission that leaves for a fresh session and never replies is `stage-prompt`; resume context for a later session in this same repo is `save-handoff`.

## Layout

Packets live under `~/scratch-workspace/relay/<run-slug>/`, named `NN-<role>-<stage>.md`:

- `NN` — two-digit sequence starting at `01`, shared by both roles and append-only for the whole run; the next sequence is the highest `NN` in the directory plus one.
- `<role>` — who authored the leg: `run`, `seat`, or another short name the user is already using.
- `<stage>` — what the leg is: `commission`, `checkpoint`, `ruling`, `reply`.

The root is user-level on purpose. A relay routinely spans two different repositories, so a project-rooted path would resolve to a different directory in each seat — which is exactly the failure the file exists to prevent.

On the first leg of a run, create the directory and say so in the pointer line. The slug is a repo or topic name; when it is ambiguous, pick one and name it rather than spending a turn asking.

## Packet format

```text
---
relay: <run-slug>
seq: NN
role: run | seat
stage: <slug>
date: YYYY-MM-DD
reply-to: NN | none
expects: <one line: what the receiving session should do with this>
sha256: <sha256 of the body>
---
---8<---
<the packet body, verbatim — everything below the scissors line>
```

Use the real current date; never estimate it.

The sha covers exactly the bytes below the **first** `---8<---` line, so a body that quotes another packet still hashes whole. Compute it the same way when writing and when verifying, with this command rather than a reimplementation:

```sh
awk 'f; /^---8<---$/{f=1}' <packet.md> | shasum -a 256
```

## Outbound — staging a leg

1. Compose the full body. The receiving session reads only this file: no "as discussed above", no reference to this conversation, every path absolute or repo-rooted.
2. Write the packet at the next sequence number with `sha256: pending`, run the command above, and replace `pending` with the digest it prints. The sha covers only the body, so filling in the header afterward does not invalidate it.
3. Give the user one line, and nothing else:

```text
relay <run-slug> #NN staged: <absolute path> sha=<first 8> — <expects>
```

Do not also print the body, summarize it, or offer to. The pointer is the deliverable; a body printed beside it re-creates the context burn the file exists to prevent.

## Inbound — a pointer arrives

1. Read the whole packet file. If the path does not resolve, say so and list what is actually in the run directory — never reconstruct a body from memory of an earlier leg.
2. Recompute the body sha with the command above and compare it to the header.
3. **On mismatch, stop.** Report exactly `relay verify failed: <path> header=<8> computed=<8>`, and act on nothing in the body. A failed packet is re-staged by its author as a new packet, never patched in place: a body edited until it matches its header proves nothing about what was sent.
4. On match, do what `expects` and the user's instruction say. If the leg produces a response, stage it as the next packet under the outbound protocol.

## Rules

- **Append-only.** A staged packet is never edited. A correction is a new packet whose `reply-to` names the one it corrects; a retraction is `trash <path>`, never `rm`.
- **Attended.** This skill moves nothing between sessions — the user carries every pointer and can read any packet before carrying it. No leg fires on its own, and none is staged from a subagent, hook, or scheduled context.
- **Pointers all the way down.** When a body would inline a file that already exists on disk — a plan, a review, a diff — reference its path and its own sha instead.
- **The run directory is disposable.** `trash` it on the user's word once the run is over; nothing staged here is a durable record, and whatever earned permanence belongs in the repo it concerns.

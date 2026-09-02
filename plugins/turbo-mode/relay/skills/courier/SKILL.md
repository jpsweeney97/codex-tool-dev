---
name: courier
description: "Use when the user is hand-carrying work between this session and another model or session — `give me a paste packet`, `prep this for Codex`, `a prompt I can paste`, `courier this` — or pastes the other side's reply back mid-relay. Composes self-contained outbound packets, then adjudicates inbound replies against local evidence before composing the next leg. Do not use when a driver automates the exchange (`/synapsis` where available), for explicit full-rigor adjudication of a supplied review (`/review-reviewer`), for first-pass review of local work, or for a multi-leg exchange between sessions sharing this filesystem (`relay-by-reference`)."
argument-hint: "[what to carry outbound | paste the other side's reply]"
---

# Courier

The user runs a relay: this session produces something, they carry it to another model — usually Codex, sometimes a fresh session of this one — and carry the reply back. **The transport is theirs; the payload is yours.** Make every leg of the trip count: outbound packets that need no follow-up question, inbound adjudication that never rubber-stamps.

Invocation: `/courier` or `$courier`, or a plain ask for something to paste elsewhere.

## The human is the wire

That is what picks this lane — but it is the wire, not the freight. When the far side shares this disk, the human still carries the leg while the payload need not travel at all: `relay-by-reference` stages each leg as a sha-stamped file and hands over one pointer line. Reach for it once an exchange runs several legs, or the body grows large enough that carrying its bytes is itself the risk — truncation, hand-transcription drift, and two sessions burning context on the same text are what that lane exists to stop. Compose the leg here under the contract below and let that skill carry it.

When a driver automates the exchange, this is the wrong skill — `/synapsis` (where available) runs a capped, certificate-producing deliberation with the machine as transport, and courier adds nothing to it. When the user pastes a formal review and wants a verdict on *that review* rather than a reply to send back, the full-rigor lane is `/review-reviewer`, and an explicit invocation of it always wins over this skill. Courier owns the round trip: adjudication here is instrumental, and exists to compose the next leg.

## Outbound — build the packet

Assume the far side has **zero context**: no memory of this conversation, no knowledge of the user, no idea which decisions are already settled. Everything it needs travels in the packet.

Settle one question before composing: **does the far side have the repo?** If it does — a Codex session in this tree — name exact paths plus the branch, commit, and dirty state, so both sides read the same bytes. If it does not, inline the artifact: a bare path is a dead reference, and the round trip is spent discovering that.

Compose one fenced block the user can copy whole.

1. **Objective** — one sentence naming what the far side is being asked to do: review, refute, decide, extend.
2. **Context capsule** — only what the far side cannot infer: the binding constraint, the decision already taken and not up for re-litigation, what the artifact is for. Ruthlessly minimal; no session narration. Withhold your own answer to the question you are asking: settled decisions travel, but a stated conclusion on the live question biases the far side toward agreeing with it, and what comes back is validation of your reasoning rather than an independent read.
3. **The artifact** — the thing itself, verbatim and complete enough to judge, or exact pinned paths when the far side can read them. Never a paraphrase of the thing under review.
4. **Response contract** — state inside the packet the shape the reply must come back in: numbered findings, each with severity, the evidence that would settle it, a proposed fix if any, and a mark on anything they could not check. An unstructured essay wastes the return trip, and an unmarked "I couldn't verify this" comes back indistinguishable from a confident assertion.

Nothing may be session-relative — no "the file we discussed", no "as above", no placeholder left for the user to fill. If the payload contains fenced code, wrap the packet in four backticks so the fences nest.

Then stop. Nothing follows the packet but at most one line on what happens next — no commentary on it, no follow-up question, no offer to do the far side's job here. The user copies, leaves, comes back.

## Inbound — adjudicate the reply

The paste is **allegations, not authority** — and, under the user's standing rule on pasted content, also a request to act rather than reference material. Both hold: verify first, act on what survives, and say plainly why anything refuted is not being acted on.

Two pulls run in opposite directions here. The far side's reply arrives fluent, confident, and *outside*, which reads as authority it has not earned — often about a tree it never opened. And the artifact under review is usually this session's own work, which makes reflexive defence exactly as cheap as reflexive deference. How a claim is written settles neither. Only local evidence does.

1. Extract every discrete claim, numbered — keep their numbering when they used one, so the reply lines up with what they sent.
2. Verify each against local evidence: read the file, run the check. **No verdict without looking.**
3. Render one of three per claim, each with its evidence pointer: **confirmed** (evidence agrees), **refuted** (evidence disagrees — report what the evidence shows, not that you disagree), **undecidable here** (name exactly what is missing and who could get it). These verdicts are for the user, who is deciding what to believe: show them in the reply rather than folding them into the outbound packet, where they are addressed to someone else.
4. Act on what is confirmed. When the confirmed list is long enough that items could go missing in the applying, hand it to `apply-findings` instead of working through it freehand.
5. Compose the next packet if the relay continues, under the same contract as outbound. Carry only the live question: what this session concluded, which claims were refuted **and the evidence that refuted them** so the far side can update, and the sharpened remainder. Settled points do not make the return trip.

## Rules of the road

- Quote the paste or nothing. Never smooth, strengthen, or fill a gap in what the far side said; a fabricated claim adjudicated as confirmed is worse than a lost round trip.
- Never send a question outward that local evidence could answer. Check first — a packet costs a trip, a file read costs nothing.
- When the same disagreement survives a second round trip, the wire has become the bottleneck rather than the argument. Say so, and name `/synapsis` (where available) as the lane built for a costly question that one reading cannot settle. Offer it; the spend is the user's call.

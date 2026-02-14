# Marching Cadence Lyrics

## Quickstart (interactive intake)

When starting a new request, ask for inputs **one at a time**. Prefer multiple choice, and only ask open-ended when necessary.

Ask in this order:

1. Topic
   - Question: “Pick the topic.”
   - Choices:
     - Cybersecurity breach (Recommended) — crisp technical nouns; easy internal echoes
     - Street-level action — physical verbs; strong staccato imagery
     - Sci‑fi operations — lots of hard consonants, gadget vocabulary
     - Political satire — punchy contrasts; careful with named real people
     - Other — user provides 1 sentence

2. Bars (length)
   - Question: “How many bars?”
   - Choices:
     - 8 bars (Recommended) — fastest iteration; easy to tighten
     - 16 bars — standard verse length
     - 4 bars — demo / proof of cadence

3. Tone / boundaries
   - Question: “What content boundaries?”
   - Choices:
     - Clean (Recommended) — no slurs, no explicit sex, no graphic violence
     - Explicit — profanity allowed; still avoid slurs
     - No threats / no violence — keeps it punchy but nonviolent

4. Payload family (rhyme target)
   - Question: “Pick a payload vowel family (the end-rhyme sound).”
   - Choices:
     - “OH-sis” (Recommended) — di-ag-NO-sis / hyp-NO-sis / os-MO-sis
     - “AY-shun” — in-va-SION / cre-A-tion / de-ba-tion
     - “UR-vis” — SER-vice / NER-vous / PUR-pose
     - Other — user provides 1–2 example words that rhyme

5. Specific payload phrase (hyphenated, 3–5 syllables)
   - Question: “Pick the payload phrase (the exact 3–5 syllable rhyme target).”
   - Choices (if family is “OH-sis”):
     - ter-mi-nal di-ag-NO-sis (Recommended)
     - deep-sea hyp-NO-sis
     - close-loop os-MO-sis
     - Other — user provides hyphenated payload

6. Anchor family (single syllable, stressed trigger)
   - Question: “Pick an anchor family (plosive, single syllable).”
   - Choices:
     - K/T attack (Recommended) — CLICK / TRICK / TICK / KICK
     - B/P attack — BRICK / PRICK / PICK / PUNCH
     - M/S attack — MAP / SNAP / SLAP / SMACK
     - Other — user provides 4 anchors (single syllable)

7. Mutation allowance (optional)
   - Question: “How much mutation across bars?”
   - Choices:
     - Anchor swaps only (Recommended) — payload stays identical
     - Anchor + connector mutations — payload identical; more narrative flexibility
     - Payload-family swaps — only if explicitly desired; risks rhyme drift

After collecting these, proceed with the main Procedure and output format below.

## Trigger / when to use

Use this skill when you need to generate rap/lyric verses with:

- A strict “marching” cadence (4/4 feel, 16-step grid per bar).
- Dense multi-syllabic rhyme (“payload”) consistency across lines.
- Visual formatting that *enforces* cadence (hyphenation, `|` caesura, bold stress, monospace alignment).

Do not use this skill when:

- The user wants natural prose, conversational lyrics, or free-flow meter.
- The user asks for copyrighted lyrics or “write like {living artist}” imitation.

## Inputs

Required:

- Topic / scene (what the verse is about).
- Payload target (a 3–5 syllable rhyme phrase, or at least the target vowel family).
- Anchor family (a sharp, stressed single syllable; plosive preferred).

Optional:

- Number of bars (default: 16 bars).
- Cadence subdivision notes (default: 16th-note grid, stress on steps 1/5/9/13).
- Allowed “mutation” set (anchor swaps, payload-family swaps, internal rhyme doubling).
- Content boundaries (clean/explicit, violence, etc.).

## Outputs

Primary output:

- A verse in a single monospace code block with:
  - Syllabic hyphenation.
  - `|` marking the half-bar caesura (8 + 8 grid).
  - **Bold** on stress points (especially anchors and payload syllables).

Secondary output:

- A short self-check table that lists each line and whether it meets:
  - “Grid plausibility” (16-step target, 8+8 caesura).
  - Anchor present and stressed.
  - Payload rhyme family consistent.
- If any line is uncertain, include a brief “cadence warning” with the suspected cause (e.g., ambiguous syllable count).

Human-first constraint (Mode A):

- Do not auto-correct lines.
- If a line fails or is uncertain, provide at most 2 alternates for that line only, labeled `ALT 1/ALT 2`.

## Procedure

### 1) Preconditions (make the grid explicit)

- Confirm the bar format: 16 slots total, split `8 | 8`.
- Confirm stress convention: emphasize steps `1/5/9/13` (and especially anchors/payload).
- Confirm payload: write it out hyphenated (e.g., `ter-mi-nal di-ag-no-sis`).
- Confirm anchor family: list 4–8 options (e.g., `MAP / TRAP / WRAP / SNAP`).

### 2) Write backward (right → left)

For each bar/line:

1. Place the **payload** at the *end* of the bar (right edge).
2. Place the **anchor** immediately before the payload (or just before the payload segment).
3. Fill the remaining slots with **connectors** (unstressed glue) that preserve meaning.
4. Add internal echoes (near-rhymes / assonance) earlier in the bar, but do not sacrifice the payload clarity.

Rule: treat words as percussion; meaning is constrained by cadence, not vice versa.

### 3) Clone and mutate (keep sound; change semantics)

Across adjacent bars:

- Keep the payload’s vowel family identical.
- Swap anchors within the anchor family.
- Mutate connectors to advance the story (new details each bar).

### 4) Format for cadence (visual spec)

Inside the monospace block:

- Use `|` exactly once per line (the breath / midpoint).
- Hyphenate multi-syllable words where the beat lands.
- Apply **bold** to:
  - Anchors (stressed trigger syllables).
  - Payload syllables (the rhyme target).
  - Optional: other primary accents aligning with 1/5/9/13.

### 5) Self-check (lint, don’t “fix”)

After the verse, produce a compact table:

- `line`: 1-based index
- `grid`: `PASS` / `WARN`
- `anchor`: `PASS` / `WARN`
- `payload`: `PASS` / `WARN`
- `note`: <= 1 short sentence when `WARN`

Guidance for `WARN`:

- If syllables are dialect-dependent or could be read multiple ways, mark `WARN`.
- If the caesura feels late/early (too many syllables on one side), mark `WARN`.

If any `WARN` exists, provide alternates only for those lines.

## Verification

Manual verification checklist:

- Each line contains exactly one `|` caesura.
- Each line clearly ends in the payload rhyme (same vowel family each bar).
- Each line has a single-syllable anchor that is bolded.
- Hyphenation makes a plausible `8 | 8` marching read.

## Failure modes

- If the user does not provide a payload: propose 3 payload candidates (hyphenated) and ask them to pick one.
- If the user does not provide an anchor family: propose 2 anchor families with different consonant attacks (e.g., `K` vs `T`) and ask them to pick one.
- If the topic conflicts with policy or the user requests imitation of a living artist: refuse the disallowed part and offer a neutral alternative (same cadence spec, original voice).
- If the cadence is ambiguous: mark `WARN` and provide limited alternates, without rewriting the whole verse.

## Examples

### Happy path (single block)

Input:

> Topic: cybersecurity breach
> Anchor family: CLICK / SWITCH / BRICK / TRICK
> Payload: ter-mi-nal di-ag-no-sis
> Bars: 4

Expected behavior:

- Outputs 4 lines in a monospace block.
- Each line uses `|` and ends in **ter-mi-nal di-ag-NO-sis** (or consistent payload segmentation).
- Produces a self-check table; warns only when genuinely uncertain.

### Edge case (missing payload)

Input:

> Topic: political satire, marching cadence, dense rhymes

Expected behavior:

- Proposes payload options (hyphenated) and waits for user choice rather than guessing.

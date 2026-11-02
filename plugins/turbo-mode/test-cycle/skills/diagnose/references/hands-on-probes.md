# Hands-on probes for non-software targets

Load this when the target is a household, hardware, appliance, tool, workflow, or AI-behavior problem and the user is the one running every probe. It replaces the software loop list in Phase 1, the tool-preference list in Phase 4, and the software cause-class table; the phases themselves, the one-variable rule, and the hard gates stand.

## The probe ladder — rank by cost, spend the cheap rungs freely

1. **Questions from memory** — what happened, what changed just before, what has already been tried.
2. **Direct observation** — look, listen, feel, smell; a photo or recording of the symptom or the failed part.
3. **Non-destructive tests** — swap in a known-good part, reseat, try a different port, outlet, or location, remove a component and retry.
4. **Cheap experiments** — deliberately trigger the problem under varied conditions.
5. **Destructive or costly probes** — last resort, cost named, explicit agreement first (see the Safety boundary in the skill body).

Each probe is written for a person's hands, eyes, and ears: say exactly what to do, what to look for, and what to report back. Prefer the probe that splits the hypothesis space over the one that flatters the favourite.

## The evidence channel by repeatability class

- **Repeatable** (fails on demand; a misbehaving prompt or skill re-run on a fixture input; a device that fails when asked): keep the loop tight — a quick trigger plus a crisp, observable pass/fail the user can repeat and report each iteration. Every iteration costs a human round trip, so minimise both the effort and the size of the report needed back.
- **Semi-repeatable** (fails often, not on command): raise the occurrence rate first (below), then run the tight loop.
- **One-shot or costly** (every retry drills another hole): reconstruct instead of reproducing — a timeline, what changed just before, photos of the aftermath, the failed part itself. Isolate on paper: which elements were present at the failure, and which does each hypothesis actually require.

## Intermittent problems — classify before retrying

The goal is not a clean trigger but a **higher occurrence rate**: a problem that shows up half the time is diagnosable; one-in-a-hundred is not. Classify the intermittency first — the cause-class names the knob that raises the rate and the probe to build. Blindly retrying wastes the budget the rate is supposed to buy.

| Cause-class | Tell | Knob that raises the rate → where the fix lives |
|---|---|---|
| **Load / stress** | Appears under heavy use, high demand, or many things at once | Deliberately increase load → capacity or overheating at the part that saturates first |
| **Environment** | Tracks temperature, humidity, season, weather, time of day, or location | Recreate the failing condition → sensitivity at the exposed component |
| **Wear / depletion** | Appears later in long use; clears after rest, restart, or replacement | Run long and watch the trend → whatever depletes: charge, heat headroom, a consumable, fatigue |
| **Leftover state / order** | Only after doing A first; fine from a fresh start | Vary the order; start clean → what A leaves behind |
| **Interaction** | Only when X and Y are combined; each is fine alone | Toggle one at a time → the mismatch at the X–Y boundary |
| **Marginal component** | No correlation at all; fails a rough fraction of attempts | Repeat attempts to measure the true rate; wiggle-test suspects → a loose, worn, or borderline part |

Match the problem to a class, then point the next probe at that class's knob. When two classes are plausible, the next probe is the one that separates them.

## Verifying the fix and watching for return

Verify against the original pinned symptom with the full scenario restored, in the user's own re-check — not against the minimised setup. For one-shot problems, define the **recurrence tell**: the earliest observable sign the problem is back, and, when the effort is worth it, a cheap periodic check that would catch it.

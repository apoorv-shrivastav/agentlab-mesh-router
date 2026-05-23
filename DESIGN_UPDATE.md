# DESIGN_UPDATE.md — Polishing the Live Console to Demo Grade

The console is deployed and the foundation is right — dark instrument-panel surface, cloud tags, monospace data. This file is the gap between *built* and *demo-ready*. It is a **punch-list, not a redesign**: targeted fixes, ordered by how much they affect the 45%-weighted live demo.

Read alongside `CONSOLE_DESIGN.md` (the authoritative spec — tokens, color language, per-view layout). This file does not replace it; it says what to fix in the thing you actually shipped.

---

## Priority 0 — The Bug That Must Be Fixed

### The ATE Effect Estimate Monitor: overlapping text

In the deployed Pipeline view, the ATE monitor renders `bounds constraint: [0-0%+10.4%]` and the `ATE +2.4%` readout **on top of each other** — collided, unreadable.

**Why this is P0, not cosmetic.** The ATE monitor *is* the demo's visceral payoff — the "confident wrong number" in Beat 2, the number that slides back in-bounds in Beat 4. It is the single object a judge's eye is meant to lock onto. A garbled headline number, on a projector, at the emotional peak of the pitch, actively undercuts the moment the whole demo is built around. Nothing else in this file matters if this is broken.

**The cause.** Two elements occupying the same space — almost certainly both absolutely-positioned into the monitor's top-right, or text laid into a track that doesn't reserve room for it. The bar and the label are not on a layout that keeps them apart.

**The fix — give the monitor a real structure.** Three stacked rows, not overlapping layers:

```
┌─ ATE EFFECT ESTIMATE MONITOR ───────────────────────────────┐
│  row 1:  ATE EFFECT ESTIMATE MONITOR        bounds: 0–10%   │  ← labels, space-between
│  row 2:  ▓▓▓▓▓▓▓▓▓●░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │  ← the bar, full width, own row
│  row 3:  0% (no-effect)      10% (max threshold)      50%    │  ← axis ticks under the bar
│                                                              │
│  current:  +2.4%   ● within bounds                          │  ← the readout, its own row
└──────────────────────────────────────────────────────────────┘
```

- Use a vertical flex/grid: label row, bar row, axis row, readout row — each a distinct row, none overlapping.
- The bar gets its **own** full-width row. Nothing is ever positioned on top of it.
- The `current: +2.4%` readout sits **below** the bar in its own row — not floated over the right edge.
- The "bounds" label goes top-right of the label row via `justify-content: space-between` — it does not float over the bar.

**The numeral.** The ATE value is the moving number. It must be monospace, `tabular-nums`, and large enough to read from the back of a room. When healthy: `--ok`. When out-of-bounds (Beat 2): `--fault`, and the dot on the bar sits visibly *past* the threshold marker. Recovery (Beat 4): it animates back inside and returns to `--ok`. (CONSOLE_DESIGN §5 — "the one number that moves.")

**Verify:** resize the browser narrow, then wide. The label and readout must never touch the bar or each other at any width. Overlap at any viewport size = not fixed.

---

## Priority 1 — Make the Broken State Unmistakable

The deployed screenshot shows the **healthy** state — every node green, ATE in-bounds, the connecting arrows plain grey. The caption already promises more: *"Warning edges represent data pollution propagation."* The demo lives or dies on whether the **broken** state delivers on that promise.

This is the cause-vs-symptom beat — the originality claim. It cannot be subtle.

**The three node states (CONSOLE_DESIGN §4.1) — confirm all three are actually built:**

- **Healthy** — `--surface-2`, hairline `--line` border, small steady `--ok` dot. (This one clearly works.)
- **FAULT — the cause** — the CAUSAL EST. node when broken: border `--fault`, a slow `--fault-glow` halo pulse around the whole node, the passRate numeral turns `--fault` and animates downward. This must be the loudest thing on the screen.
- **CONTAMINATED — the symptom** — the READOUT node when broken: border `--warn`, lighter `--warn-glow`, **and an inline tag reading `input from CAUSAL ↑`** so it explicitly says its trouble came from upstream. Amber, not red — and it says why.

**The propagation edge.** The grey arrow between CAUSAL and READOUT is, right now, just an arrow. In the broken state it must **animate**: a directional `--warn` pulse travelling cause → symptom, repeating. This is the most important 200 pixels in the demo — it is what makes "the failure propagates downstream" something a judge *watches* rather than something you assert. A static arrow cannot carry Beat 2.

**The test:** put the broken state on screen and look away, then back. In one second, can someone who has never seen the app point at the cause? If yes — red node, amber pulse flowing out, amber node labelled `input from CAUSAL ↑` — the view is doing its job. If the broken state looks much like the healthy state, Beat 2 has no punch and this is the most important thing to fix after P0.

---

## Priority 2 — Fluidity: Motion and Transitions

"Fluid" comes from *transitions between states*, not from more decoration. Right now state changes likely **snap**; they should **resolve**.

- **State transitions, ~400–600ms ease.** When a node goes healthy → fault, the border colour, the glow, and the numerals should transition over ~500ms — not jump. Cause heals before symptom in Beat 4; that ordering is only legible if each transition is slow enough to see. `transition: border-color 500ms ease, box-shadow 500ms ease;`
- **The ATE dot glides.** When the estimate moves out of / back into bounds, the dot travels along the bar over ~1.2s — it does not teleport. The numeral counts up/down with it (tabular figures, so no width jitter).
- **View switches don't flash.** Moving Pipeline → Triage → Pareto should be a quick crossfade or slide (~200ms), not a white flash or hard cut. A flash on every beat transition reads as "web page"; a smooth change reads as "instrument."
- **One motion at a time.** During a demo beat, exactly one thing animates — the thing you're talking about. Kill idle/ambient animation; it competes with the moment that matters. Respect `prefers-reduced-motion` with a coherent no-motion fallback.
- **The triage reasoning streams.** In the Triage view the agent's reasoning must appear token-by-token, visibly (CONSOLE_DESIGN §4.2). A spinner that resolves to a finished block reads as a database query; streaming reads as an agent thinking. This *is* the originality beat — it must feel alive.

---

## Priority 3 — Consistency and Finish

Small things that separate "polished" from "hackathon":

- **One spacing scale.** Everything on an 8px grid — card padding, gaps, margins. Inconsistent gaps are the most common "unfinished" tell. Pick `8 / 16 / 24 / 32` and hold to it.
- **Align the metric rows.** passRate / queryCost / latency across the three nodes should sit on a perfectly shared baseline and column rhythm. Monospace + `tabular-nums` on every number so nothing shifts when values animate.
- **Hairline borders, not heavy boxes.** `1px solid var(--line)`. Depth comes from the surface layers (`--surface-1/2/3`) and soft large-radius shadows — not thick outlines.
- **Consistent corner radius.** One radius for cards (e.g. 12px), one smaller for chips/tags (e.g. 6px). Two values total.
- **Typography discipline.** Headings in the display face; all data in monospace; body/labels in the grotesk. No Inter/Arial/system-ui anywhere (CONSOLE_DESIGN §2). Labels like `passRate` in `--ink-mid`, values in `--ink-hi` or a state colour — a clear hierarchy, not flat uniform text.
- **The status bar.** Confirm the persistent global health pill (`● PIPELINE HEALTHY` → `▲ DEGRADATION DETECTED`) and the loop-state indicator exist (CONSOLE_DESIGN §3). A judge should be able to follow the whole demo from that bar alone. If it's not built, it's a high-value small add.
- **Empty / loading states.** Any view fetching data needs a deliberate skeleton or quiet "loading…" — never a flash of empty layout or a raw spinner on white.

---

## What NOT to Do

- **Don't redesign.** The instrument-panel direction is working. This is tightening, not reinvention. A from-scratch restyle the night before judging is how you arrive with a half-finished console.
- **Don't add colour.** The palette is intentionally tight — surfaces, ink, and exactly four state colours. Resist accent colours, gradients-for-decoration, multi-hue charts. Restraint *is* the aesthetic.
- **Don't gold-plate Signals/Router.** Pipeline, Triage, Pareto carry the demo. Signals and Router need only be clean and on-theme. Spend the polish budget where the 45% is.
- **Don't animate for its own sake.** Every animation must carry meaning — a state change, a value moving, an agent thinking. Decorative motion competes with the demo and cheapens it.

---

## The Order of Work

1. **P0 — fix the ATE monitor overlap.** Nothing else ships until the headline number is readable. ~30–60 min.
2. **P1 — the broken state.** Fault node, contaminated node, animated propagation edge. This is the demo's punch. The biggest item here.
3. **P2 — transitions.** Make state changes resolve over ~500ms instead of snapping. Medium effort, large payoff in "fluid."
4. **P3 — consistency sweep.** Spacing, alignment, borders, typography. An hour of finish work.

Then re-run the `CONSOLE_DESIGN.md` §6 visual checklist against the deployed URL, on a projector or external display if you can — that is the surface judges see, and it is not the same as your laptop screen.

---

## The One-Line Test

After every change, ask the only question that matters for a 45%-live-demo score:

> On a projector, at the back of the room, can someone who has never seen this app watch the broken state appear and point at the step that caused it — in one second?

When the answer is yes, the console is demo-ready.

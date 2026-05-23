# CONSOLE_DESIGN.md — Visual Spec for the AgentLab Console

This is the design contract for the console. It exists so the day-of build executes a deliberate visual, not an improvised one. Live Demo is **45%** of the score and the console *is* the live demo — this file is as load-bearing as SCAFFOLD.md.

The single rule that governs everything below: **the headline claim must be visible, not narrated.** "The triage agent localized the fault to the *cause* step, not the *symptom* step" is an abstract relationship. If a judge has to take your word for it, the originality beat (35%) is wasted. Every choice here serves making that relationship something a judge sees across the room in one second.

---

## 1. Aesthetic Direction

**Direction: instrument panel, not dashboard.** Think aircraft glass cockpit or a trading terminal — a dark, dense, precise surface where state is read at a glance and a change in state is *alarming*. This is not a marketing site and not a generic admin panel. It is a diagnostic instrument, and it should feel like one: calm when healthy, unmistakably loud when something breaks.

Why this direction: it matches the product (a fault-detection system), it photographs well on a projector, and it is the opposite of the gray-box Recharts dashboard 40 other teams will show. Commit to it fully — restraint and precision, not decoration.

**Theme: dark.** Near-black background, high-contrast foreground. Dark is correct here for three reasons: a red/amber alarm state pops violently against it, it reads as "operations tooling" rather than "consumer app," and it survives a badly-calibrated projector better than light themes.

**One thing a judge remembers:** the moment the broken step goes red and the propagation arrow carries an amber "contaminated" pulse downstream into a step that is *itself* still green. Cause and symptom, in one frame. Build the whole console outward from making that one frame unmistakable.

---

## 2. Design Tokens

Define these as CSS variables once; never hardcode a hex value in a component. Consult the **frontend-design skill** for the environment's constraints before building.

### Color

```css
:root {
  /* Surfaces — near-black, slightly cool, layered for depth */
  --surface-0:  #0B0E14;   /* app background */
  --surface-1:  #12161F;   /* panel background */
  --surface-2:  #1A2030;   /* raised card / node background */
  --surface-3:  #232B3D;   /* hover / active raise */

  /* Ink */
  --ink-hi:     #E6EAF2;   /* primary text */
  --ink-mid:    #9AA4B8;   /* secondary text, labels */
  --ink-lo:     #5C6679;   /* tertiary, axis ticks, disabled */

  /* State — the alarm language. Used sparingly, with intent. */
  --ok:         #3DD68C;   /* healthy. green. calm. */
  --warn:       #F2B544;   /* amber. "contaminated" / propagated failure. */
  --fault:      #F2555A;   /* red. THE BROKEN STEP. the cause. */
  --info:       #5B9DFF;   /* routing decisions, neutral agent activity */

  /* State glows — same hues at low alpha for halos/pulses */
  --ok-glow:    rgba(61, 214, 140, 0.16);
  --warn-glow:  rgba(242, 181, 68, 0.18);
  --fault-glow: rgba(242, 85, 90, 0.22);

  /* Lines */
  --line:       #2A3247;   /* hairline borders, grid */
  --line-hot:   #3A4663;   /* active borders */
}
```

The discipline that makes this work: **red means exactly one thing — the step that caused the failure.** Never use red for a warning, a button, or a chart line. Amber means exactly one thing — a failure *propagated* from elsewhere, i.e. a symptom. Green means healthy. If you hold that line, the Pipeline view becomes literally self-explaining: red is the cause, amber is the symptom, and the demo's whole thesis is pre-narrated by the color.

### Typography

Do **not** use Inter, Roboto, Arial, or system-ui — they read as "AI default." Pair two distinctive fonts:

- **Display / headings / the moving number:** a precise, slightly technical sans — e.g. **Space Mono** (yes, mono as a display face — instrument-panel feel) or **Archivo** / **Archivo Expanded** for headers. Pick one and commit.
- **Body / labels / dense data:** a clean grotesk with good small-size legibility — e.g. **IBM Plex Sans**.
- **Numerals everywhere data lives:** a monospace — **IBM Plex Mono** or **JetBrains Mono**. All metrics, scores, latencies, and especially the recovering effect estimate must be monospace and **tabular-figure** aligned (`font-variant-numeric: tabular-nums`) so digits don't jitter when they animate.

Load from a CDN. If a font fails to load, the fallback should still be a deliberate choice, not Arial.

### Space, line, motion

- 8px spatial grid. Dense, but every element on a multiple of 8.
- Hairline borders (`1px var(--line)`), not heavy boxes. Depth comes from surface layering and shadow, not outlines.
- Shadows are soft and large, low-alpha — atmosphere, not drop-shadow clip-art.
- Motion is purposeful and rare. One orchestrated transition per demo beat. No idle micro-animations competing with the moment that matters. The `prefers-reduced-motion` path should still be coherent.

---

## 3. Layout Shell

A persistent shell around all five views:

```
┌──────────────────────────────────────────────────────────────┐
│  AgentLab        ● PIPELINE HEALTHY            ⟳ loop: idle    │  ← status bar
├────────┬─────────────────────────────────────────────────────┤
│        │                                                       │
│  ▸ Pipeline                                                    │
│  ▸ Triage          [ the active view fills this region ]       │
│  ▸ Signals                                                     │
│  ▸ Router                                                      │
│  ▸ Pareto                                                      │
│        │                                                       │
└────────┴─────────────────────────────────────────────────────┘
```

- **Left rail:** the five views. Keep this order — it is the demo order. The active view's label is `--ink-hi`; the rest `--ink-mid`.
- **Status bar:** one global health pill and one loop-state indicator. This is the demo's *ambient drama* — when the failure is triggered, `● PIPELINE HEALTHY` (green) flips to `▲ DEGRADATION DETECTED` (red), and the loop indicator advances through `idle → detecting → localizing → awaiting approval → re-scoring → recovered`. A judge can follow the entire demo from this bar alone. Make it prominent.
- During the demo you navigate views manually — but the status bar makes the *system's* state legible independent of which view is up.

---

## 4. The Five Views

Demo-critical, in priority order: **Pipeline, Triage, Pareto.** If the build runs short, Router and Signals can be thinner — but the three above must be fully realized. (FALLBACK.md says the same.)

### 4.1 Pipeline — *the headline view*

This is the view the cause-vs-symptom story lives or dies on. It must carry beats 1, 2, and 4 of the demo.

**Layout.** The three step-agents as horizontal **nodes**, large, left-to-right, connected by **flow edges**. Not small boxes — substantial cards, each showing: step name, agent ID, cloud tag, and three live mini-metrics (quality, cost, latency) in monospace.

```
   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │  DATA PREP  │━━━━━━━▶│   CAUSAL    │━━━━━━━▶│   READOUT   │
   │  ● gcp      │  edge  │   EST.      │  edge  │  ● azure    │
   │             │        │  ● aws      │        │             │
   │ q  0.94     │        │ q  0.91     │        │ q  0.93     │
   │ $  0.002    │        │ $  0.011    │        │ $  0.004    │
   │ ms 240      │        │ ms 1180     │        │ ms 600      │
   └─────────────┘        └─────────────┘        └─────────────┘
```

**The three states a node can be in — this is the core of the spec:**

1. **Healthy** — `--surface-2` background, thin `--line` border, a small steady `--ok` dot. Calm. Unremarkable.
2. **FAULT (the cause)** — the broken step. Border becomes `--fault`, a `--fault-glow` halo pulses slowly around the whole node, the quality metric turns `--fault` and its digits animate downward. This node should be the loudest thing on the screen. When a judge glances over, their eye goes here first.
3. **CONTAMINATED (the symptom)** — a step that is *itself behaving correctly* but is receiving bad input. Border becomes `--warn`, a lighter `--warn-glow`. Critically: a small inline tag on the node reads **"input from CAUSAL ↑"** — it explicitly names that its trouble comes from upstream. The node is amber, not red, *and it says why.*

**The edges carry the propagation.** The flow edge from the faulted step to the contaminated step is the most important 200 pixels in the demo. When the failure triggers, that edge animates: a directional `--warn` pulse travels along it, cause → symptom, repeatedly. The edge *shows* the contamination flowing. A static line cannot do this; the animated edge is what makes "the fault propagates downstream" a thing the audience watches rather than hears.

**So in beat 2, without you saying a word, the screen reads:** one red pulsing node (the cause), an amber pulse flowing out of it along the edge, into an amber node that is labeled "input from CAUSAL ↑" (the symptom). The judge has understood your originality claim before you finish the sentence. Then you say it, and it lands as confirmation, not assertion.

**Beat 4 (recovery):** the router reroutes; the faulted node visibly swaps its agent ID to the healthy spare; over ~1.5s the border transitions `--fault → --ok`, the halo fades, the quality digits climb back up. The contaminated node follows a beat later — amber → green, the "input from CAUSAL ↑" tag fades out — because its input is clean again. Recovery propagates the same direction the failure did. Cause heals first, symptom heals second. That sequence is itself an argument.

### 4.2 Triage — *the originality beat*

This view carries beat 3. It has to make an agent *reasoning* feel real, and make *localization* feel like a conclusion, not a lookup.

**Layout: three stacked zones.**

1. **Reasoning stream (top).** As the triage agent runs, its reasoning **streams in token by token** into a monospace panel — visibly, not behind a spinner. This is the "this is a real agent thinking" moment; a spinner that resolves to a result reads as a database query. Let it stream even if you have to throttle it slightly for legibility. Style it like a terminal log: `--ink-mid` text, `--info` for the agent's own callouts, timestamped lines.

2. **Localization verdict (middle) — the centerpiece.** When reasoning resolves, a verdict card snaps in with a deliberate animation. It must visually commit to an attribution:

   ```
   ┌────────────────────────────────────────────────┐
   │  FAULT LOCALIZED                                 │
   │                                                  │
   │   CAUSAL ESTIMATION  ◀── cause     [red chip]    │
   │   READOUT            ── symptom    [amber chip]  │
   │                                                  │
   │  root cause:  effect estimates fall outside      │
   │  plausible bounds after model upgrade; readout    │
   │  faithfully propagated the contaminated input.    │
   │                                                  │
   │  confidence: out-of-bounds oracle — provable      │
   └────────────────────────────────────────────────┘
   ```

   The two-line cause/symptom split here mirrors the Pipeline view's red/amber exactly. Same color language, second time — repetition is what makes it stick. The word "provable" earns its place: it's your statistical-rigor signal, on screen.

3. **Generated eval cases + Approve (bottom).** The 3–5 drafted tasks appear as cards. Each is clearly *new* (a subtle `--info` "drafted" tag). The **Approve** button is the only prominent interactive control in the whole console — give it real weight, `--ok` fill, a satisfying press state. When clicked: the cards get a green check, the status bar advances to `re-scoring`, and the view is ready to cut back to Pipeline for the recovery. The click should *feel* like committing something.

Make explicit in the UI that approval is a human gate — a small line like `human review required — triage proposes, you dispose`. The supervised-by-design point from the README should be visible here, not just spoken.

### 4.3 Pareto — *the close*

Beat 5. A cost-vs-quality scatter/curve: x = cost per call, y = quality. The learned router's frontier curve sits visibly above and left of the baseline's.

This is the one view where a chart is right — but do **not** ship default Recharts. Restyle completely: dark canvas, `--line` grid at low contrast, axis labels in monospace `--ink-lo`, the baseline curve in muted `--ink-mid`, the learned curve in `--ok` and thicker, with its points glowing faintly. On entry, animate the learned curve drawing itself in over ~800ms so the dominance *reveals* rather than just being present.

One annotation callout on the chart pointing at the gap between the curves: `learned router — same quality, ~40% less cost` (use your real number). One callout, not five.

### 4.4 Signals — *supporting*

Per-step signal rates over time — small multiples, one sparkline strip per signal (tool-error, latency, the classifiers, out-of-bounds). When the failure triggers, the relevant sparklines spike and the out-of-bounds strip crosses a marked threshold line. Useful for Q&A drill-down ("how did you detect it?") but not a demo-critical beat. Functional, on-theme, doesn't need the polish budget the top three do.

### 4.5 Router — *supporting*

A live decision feed: each routing decision as a row — step, chosen agent, the alternatives considered, predicted P(success), cost, and a one-line `--ink-mid` explanation. When the reroute fires in beat 4, a new row animates in at the top showing the swap to the healthy agent. Nice corroboration of the recovery; not load-bearing.

---

## 5. The One Number That Moves

Every demo needs a single visceral number. Yours is **the causal effect estimate** going from out-of-bounds to in-bounds.

Treat it as a designed object, not a table cell:

- Render it large, monospace, tabular-figure, somewhere persistently visible during the recovery beat — on the Causal node and ideally echoed in the status region.
- Show it **against its bounds**: a small horizontal track with the plausible range marked, and the estimate as a dot on that track. Broken = the dot is *outside* the marked range and `--fault`. Recovered = the dot slides back *inside* the range and turns `--ok`.
- When recovery fires, animate both at once: the dot travels back into bounds over ~1.2s while the numeral counts from the wrong value to the correct one (tabular figures, so no width jitter). End on a brief `--ok-glow` pulse.

That motion — a wrong red number visibly sliding home and turning green — is what a judge describes to the other judges afterward. It is worth disproportionate polish.

---

## 6. What "Done" Looks Like

A pre-demo visual checklist (pair it with VALIDATION §9):

- [ ] No Inter / Roboto / Arial / system-ui anywhere. Two deliberate fonts loaded; numerals are monospace + tabular.
- [ ] Red appears **only** on the cause step. Amber appears **only** on propagated/symptom state. No exceptions anywhere in the UI.
- [ ] On a projector at presentation distance, the red cause node and the amber-pulsing edge are identifiable in **one second** by someone who has never seen the app.
- [ ] The triage reasoning visibly streams; it does not resolve from a spinner.
- [ ] The localization verdict card states cause vs. symptom in the same color language as the Pipeline view.
- [ ] The Approve button is the clear primary action and the human-gate framing is visible on screen.
- [ ] The effect estimate animates against its bounds — out-and-red to in-and-green — on recovery.
- [ ] Recovery propagates cause→symptom, mirroring the failure direction.
- [ ] No idle animation competes with the active demo beat.
- [ ] The status bar alone tells the whole story if someone watches only that.
- [ ] Pareto is fully restyled — no stock Recharts palette.

---

## 7. Build Order (fits the rehearsal-then-rebuild plan)

Console polish is real work — budget it, don't leave it to the last 30 minutes. In the day-of rebuild:

1. **Tokens + shell first.** CSS variables, fonts, layout shell, status bar. One hour, and everything after inherits the aesthetic for free.
2. **Pipeline view to full polish.** The three node states, the animated propagation edge, the recovery transition. This is the headline — it gets the most time.
3. **Triage view to full polish.** Streaming reasoning, the verdict card, the Approve interaction.
4. **The moving number.** The bounds track and its animation — small surface, high payoff.
5. **Pareto**, restyled properly.
6. **Signals and Router** — functional and on-theme; stop when they're clean, don't gold-plate.

If time runs short, a fully-polished Pipeline + Triage + Pareto with described Signals/Router beats five mediocre views. Depth on the three that carry the demo, every time.

# FINAL_DESIGN.md — Console Front-End Polish

Instructions for the coding agent. **Scope: front-end visual changes only.** Do not touch state logic, API calls, data fetching, the demo flow, or `simState` handling. This file changes how the console *looks and feels* — nothing about how it *works*.

## The Goal

The console currently reads as a **terminal**. It should read as a **product** — a polished diagnostic instrument. The cause is one decision: nearly every text element uses a monospace font. The fix is to use monospace only where it belongs (numbers, logs, code) and a clean sans-serif everywhere else (labels, headings, prose).

Apply the changes below in order. #1 does most of the work.

## Files In Scope

- `console/src/app/page.tsx`
- `console/src/app/globals.css`
- `console/src/app/layout.tsx`

The fonts are already loaded in `layout.tsx` (Space Mono, IBM Plex Sans, IBM Plex Mono) and wired in `globals.css` under `@theme inline` as `--font-display`, `--font-sans`, `--font-mono`. No font loading changes needed — this is purely about *which* font is applied where.

---

## Change 1 — Demote Monospace to Data Only (the big one)

**Rule:** monospace is for *values, numbers, logs, and code identifiers*. Everything else — labels, descriptions, headings, nav, prose — uses sans-serif (`font-sans`, IBM Plex Sans).

**Keep `font-mono` on (do NOT change these):**
- The metric *values*: passRate `0.98`, queryCost `$0.002`, latency `120ms` numbers.
- The ATE estimate number (`+2.4%` / `+48.5%`).
- The streaming triage terminal content (`triage_reasoner_shell` log lines).
- The router table *cell values* (request IDs, P(success), cost numbers).
- Small technical identifiers/tags where mono aids legibility (cloud tags `● GCP`, run IDs).

**Switch to `font-sans` everywhere else** — change `font-mono` and `font-display` to `font-sans` on:
- The metric *labels*: `passRate`, `queryCost`, `latency` (the small caption text above each value).
- The `agent:` label and the agent-name value in each node.
- The `bounds constraint:` label text in the ATE monitor.
- The ATE monitor axis tick labels (`0% (no-effect)`, `10% (max threshold)`, etc.) — these can stay mono if they read as data, but the descriptive ones move to sans.
- The `current estimate:` label (the number after it stays mono).
- The loop-state indicator label `loopState:` (the value stays).
- Any descriptive sentence or helper text currently in mono.

The visual result: **sans-serif labels, monospace values.** That contrast is what reads as "instrument panel" instead of "terminal." This single change is ~80% of the improvement.

## Change 2 — Headings to Sans-Serif

All section headings currently use `font-display` (Space Mono). Monospace headings read as code comments, not product UI.

- Change all `<h1>`, `<h2>`, `<h3>` and heading-like elements from `font-display` to `font-sans` with `font-weight: 600` or `700`.
- This includes: "Routing Flow Architecture", "Autonomous Triage Workspace", "Multi-Agent Pareto Optimization", "Real-Time Signal Telemetry", "Decentralized Router Decision log", the "AgentLab" wordmark in the header and end card, and the sidebar nav labels.
- Keep the letter-spacing tasteful — heavy tracking on sans headings looks dated; reduce `tracking-wider` to `tracking-tight` or normal on headings.

After Changes 1 and 2, `font-display` (Space Mono) may be used very little. That is fine — leaving it loaded is harmless.

## Change 3 — Depth From Elevation, Not Borders

The console currently builds depth from `1px` borders everywhere, which reads as terminal/wireframe. Shift to soft elevation.

- On raised cards (`bg-surface-2` nodes, the ATE monitor, the verdict card, signal cards): keep a *subtle* border but add a soft shadow — large blur radius, low opacity, e.g. `box-shadow: 0 4px 24px rgba(0,0,0,0.4)`. Cards should feel like they float on the `--surface-0` background.
- Reduce reliance on visible hairlines between sections — let the surface-layer contrast (`--surface-0` vs `--surface-1` vs `--surface-2`) and shadow do the separating.
- Keep borders only where they carry meaning: the state borders (fault red, warn amber) on nodes must stay — those are semantic, not decoration.

## Change 4 — More Breathing Room

Terminal density is part of the terminal feeling. Open it up.

- Increase card interior padding: `p-4` → `p-5` or `p-6` on the node cards, the ATE monitor, the verdict card, the signal cards.
- Increase the vertical gap between major sections — particularly between the three-node row and the ATE monitor in the Pipeline view.
- Increase the gap in the metric grids (`gap-2` → `gap-3` or `gap-4`).
- Keep everything on a consistent 8px-multiple scale (8 / 16 / 24 / 32). Do not introduce arbitrary values.

White space should feel deliberate and generous. Density reads as tooling; space reads as design.

## Change 5 — Remove Literal Terminal Cosplay

The Triage streaming log *should* look like a terminal — that is its correct nature; leave the streaming log content and its monospace styling alone.

But remove the decorative window-chrome cliché:
- Remove the three coloured "traffic light" dots (red/amber/green circles) in the triage panel header. Replace with a clean, simple header bar — a small label and nothing else.
- The panel header label can stay informative but make it calmer — a simple title rather than a fake `.log` filename styled as system chrome.
- The streaming log body itself stays exactly as is. It is the one place a terminal aesthetic is correct.

## Change 6 — Calm the Idle Animations

Constant ambient motion reads as a noisy dashboard. Motion should mark *what is actively happening*, not decorate idle states.

- Remove `animate-pulse` from the **healthy** state header dot and any other idle/stable element. A healthy system should be visually *still*.
- Keep the pulsing glow animations (`animate-fault-glow`, `animate-warn-glow`) — those mark an active fault and are correct.
- Keep the streaming-cursor blink and the flow-edge animation — those mark active processes.
- The rule: if it's not actively happening *right now*, it should not be moving. Stillness in the healthy state makes the alarm states land harder by contrast.

## Change 7 — Small Consistency Fixes

- The `glassmorphism` class is currently applied to only the Data Prep node, while the other two nodes use plain `bg-surface-2`. Make the three nodes **identical** in treatment — remove `glassmorphism` from the Data Prep node so all three match (plain `bg-surface-2`). Consistency matters more than the blur effect, and dropping it also helps render performance.
- Ensure all three node cards have identical padding, radius, border weight, and shadow. They are siblings; they must look like siblings.
- Use one corner radius for cards (e.g. `rounded-xl`) and one smaller radius for chips/tags/buttons (e.g. `rounded-md`). Two values total across the app.
- Ensure the metric rows (passRate / queryCost / latency) align perfectly across all three nodes — same baseline, same column widths.

---

## What NOT To Change

- **No state logic, no API code, no data fetching, no `simState` flow.** Front-end visuals only.
- **Do not change the colour tokens.** The palette in `globals.css` is correct — surfaces, ink, four state colours. Do not add colours, gradients, or accents.
- **Do not restructure the views or the layout.** The shell (header / sidebar / workspace) and the six views stay exactly as they are structurally.
- **Do not touch the streaming triage log's content or its monospace styling** — only its decorative window-chrome header.
- **Do not "improve" the ATE monitor's four-row structure** — it is correct.
- This is a polish pass, not a redesign. Keep every change incremental and visual.

## Order of Work

1. **Change 1** — mono → sans on all labels/prose. The biggest visual win. Do this first and view the result.
2. **Change 2** — headings to sans-serif.
3. **Changes 3 & 4** — elevation and spacing. The "designed, not built" layer.
4. **Changes 5, 6, 7** — terminal-chrome removal, idle-motion cleanup, consistency.

After each change, view the deployed console and confirm nothing structural broke. The test for success: **does it look like a product a company would ship, or a terminal a developer left open?** When it's the former, stop.

# QR_ENDCARD.md — Repo QR Code & Demo End Card

A small, self-contained addition: a QR code linking judges to the source repo, presented as an **end card** shown after the demo's final beat. ~15–20 minutes of work.

Read alongside `CONSOLE_DESIGN.md` (tokens, aesthetic) and `PITCH.md` (the demo script — the end card follows Beat 5).

---

## 0. Before You Build — Verify the Target

Two checks first; a QR code to a broken target is worse than no QR code:

1. **The repo is public and resolves.** Confirm `https://github.com/apoorv-shrivastav/agentlab-mesh-router` actually loads in an incognito window. A QR to a 404 or a private repo, scanned in front of judges, is a bad look.
2. **The repo is in presentable shape.** A QR code is an invitation to inspect — judges *will* scan it. Before it goes on screen, confirm: the README is the current localization-centered version, the "what did you build today" story is clean (day-of code committed on the day), the `docs/METHODOLOGY.md` pre-registration is present, and there are no stray credentials anywhere in the git history.

> **Naming note.** The product is **AgentLab**; the repo is `agentlab-mesh-router` (the infra name). A judge who scans sees "mesh-router," not "AgentLab." This is consistent with the project's naming rule and is fine. If renaming the repo to `agentlab` is quick and clean, it makes the QR destination match the product name — a minor nicety, not worth a risky rename this late.

---

## 1. What This Is

A **dedicated end card** — a final view (or full-screen overlay) the presenter switches to *after* Beat 5, holding three things:

- The closing line from the pitch.
- The QR code → the repo.
- Name and one-line identifier.

It is **not** a QR code tucked into the Pipeline or Triage views. During the 3-minute demo every pixel serves the localization story; a QR code sitting in a live view is noise competing with the ATE monitor. As an end card it earns its place: it is the thing left on screen during Q&A, while judges are forming their impression and deciding whether to follow up.

---

## 2. Building the QR Code

For the React/Next console, use `qrcode.react` — renders an inline SVG, crisp at any size, no network call (works even on venue wifi), themeable.

```bash
pnpm add qrcode.react
```

```tsx
import { QRCodeSVG } from "qrcode.react";

<QRCodeSVG
  value="https://github.com/apoorv-shrivastav/agentlab-mesh-router"
  size={180}
  bgColor="#FFFFFF"      // QR codes scan most reliably on white
  fgColor="#0B0E14"      // --surface-0, near-black
  level="M"              // error-correction; M is the standard balance
  marginSize={2}         // a quiet zone — scanners need the white border
/>
```

Notes:
- **Keep the QR itself on a white background.** Dark-on-dark QR codes scan poorly. The white square sits *inside* a dark themed card — the card is themed, the code stays white.
- `size={180}` reads well on a projector from across a room. Do not shrink it below ~140px.
- `level="M"` is fine. No need for `H` unless you overlay a logo (don't — keep it clean).
- No API key, no external request, no dependency on connectivity.

If you would rather avoid the dependency entirely, an `<img>` pointing at a QR-generator service works — but `qrcode.react` renders offline, which is the safer choice in a venue. Prefer it.

---

## 3. The End Card Layout

Full-bleed, centered, on `--surface-0`. Calm and confident — this is the last thing judges see.

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                      AgentLab                           │   ← display face, large
│        step-level fault localization for                │   ← --ink-mid, one line
│            multi-agent pipelines                        │
│                                                          │
│              ┌──────────────────┐                       │
│              │                  │                       │
│              │   [ QR CODE ]    │   ← white, on a       │
│              │                  │      --surface-2 card  │
│              └──────────────────┘                       │
│              scan for the source →                      │   ← monospace, --ink-mid
│                                                          │
│   "When an agent pipeline gives you a confident wrong    │   ← the closing line,
│    answer, the question that matters is which step,      │      --ink-hi, quoted
│    and how do you know."                                 │
│                                                          │
│         Apoorv Shrivastav · Senior Data Scientist        │   ← --ink-lo, small
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- The QR sits on a `--surface-2` card with a hairline `--line` border and the same corner radius as the console's other cards — it belongs to the same design system.
- Label it: `scan for the source →` in monospace `--ink-mid`. Judges should not have to guess what it is.
- The closing line is the one from `PITCH.md` Beat 5 — so the card *reinforces* the spoken close rather than introducing new text.
- Typography per `CONSOLE_DESIGN.md` §2 — display face for "AgentLab," monospace for the label, the grotesk for the tagline. No Inter/Arial.
- No animation needed. The end card is a resting state; let it be still.

---

## 4. Wiring It In

Two options, simplest first:

**Option A — a sixth route.** Add `console/app/end/` as a plain view. The presenter navigates to it after Beat 5. Simplest; nothing else changes.

**Option B — an overlay.** A full-screen overlay toggled by a keypress or a corner control, so it can be summoned from any view. Slightly more work; useful if you want to bring it up flexibly during Q&A.

Option A is enough. The demo script already ends on the Pareto view — add one step: after the Beat 5 line, switch to the end card and leave it there for Q&A.

If you want it discoverable without the presenter driving (e.g. judges exploring the shared link), also place a small, unobtrusive QR or a link to the end card in the console footer — small, `--ink-lo`, never competing with a live view.

---

## 5. One Line for the Demo Script

Add to `PITCH.md` Beat 5, after the closing line — delivered while switching to the end card:

> *"Everything you've seen is open — the repo's on screen, scan it."*

Then leave the end card up. It puts the repo and your name in front of the judges at the exact moment they are deciding whether to find you afterward — which, per the pitch's own framing, is the actual goal.

---

## 6. Checklist

- [ ] Repo is public and loads in an incognito window.
- [ ] Repo content is presentable (README current, day-of-build story clean, no credentials in history).
- [ ] QR scans reliably — test with an actual phone, from projector distance, before judging.
- [ ] QR is white-on-dark-card, ≥140px, with a quiet-zone margin.
- [ ] End card uses the console's design tokens — it belongs to the same system.
- [ ] The closing line on the card matches `PITCH.md` Beat 5.
- [ ] The presenter knows the one extra step: after Beat 5, switch to the end card.

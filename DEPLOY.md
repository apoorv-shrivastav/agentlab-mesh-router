# DEPLOY.md — Deploying AgentLab to Cloud Run

This covers putting AgentLab on Cloud Run so it has a public HTTPS URL — both for the demo you drive on stage and for a link you hand to judges.

Read this alongside `SETUP.md` (the cloud infra), `SCAFFOLD.md` (which already deploys the router as its own service), and `FALLBACK.md` (the collapse plan).

---

## 0. The Decision That Comes First

There are **two different things** you might mean by "deploy the demo," and they have different requirements. Decide which you are building — or build both, clearly labelled.

| | **A. Stage demo** | **B. Judge-shareable link** | **C. Fallback snapshot** |
|---|---|---|---|
| Who drives it | You, narrating, once | Judges, alone, unprompted, possibly at the same time | Nobody — it's a frozen artifact |
| Data source | BigQuery + live agents | BigQuery + live agents, **per-session isolated** | SQLite baked into the image |
| Loop writes | Yes — to BigQuery | Yes — but must not corrupt other visitors | None — read-only |
| State after the loop runs | Persists, you reset between rehearsals | **Must auto-reset or isolate** | N/A — always shows the pre-baked state |
| Honest claim | "Running live, across three clouds" | Same | "A recorded run — here's the system" |
| Purpose | The 3-minute judged demo | Extra credit; judges explore after | Safety net if A breaks on stage |

**A and B are nearly the same build** — same services, same BigQuery backing — and B just adds session isolation or a reset. **C is the SQLite single-container build**; it is your `FALLBACK.md` asset, not your main demo. Build C *as well*, but never present C as if it were live.

> **The trap.** A baked-in SQLite snapshot deployed as the "main demo" looks live but isn't — and the loop's writes (Approve, re-score, reroute) vanish on Cloud Run's ephemeral, per-instance filesystem. One judge question — *"is this running live right now?"* — and the one dishonest thing in an otherwise honest project unravels. The main demo must be true. Use BigQuery.

This file covers **A and B**. For C, see the single-container note in §7.

---

## 1. Architecture: Separate Services, Not One Container

Cloud Run expects **one process per service**, answering on `$PORT`. Do not pack the Next.js console and a Python bridge into one image with one backgrounded — if the backgrounded process dies, Cloud Run cannot see it or restart it, and the console goes half-dark mid-demo.

Three services (the router is already in `SCAFFOLD.md`'s deploy steps):

```
   judge's browser
        │
        ▼
  ┌───────────────┐     calls by URL    ┌────────────────────┐
  │  CONSOLE      │ ──────────────────▶ │  ROUTER /          │
  │  (Next.js)    │                     │  ORCHESTRATOR      │
  │  Cloud Run    │                     │  (Python, FastAPI) │
  └───────────────┘                     │  Cloud Run         │
                                        └─────────┬──────────┘
                                                  │
                          ┌───────────────────────┼───────────────────┐
                          ▼                       ▼                   ▼
                    BigQuery (mesh,        data-prep agent      causal agent (AWS)
                    evals datasets)        (Cloud Run, GCP)     readout agent (Azure)
```

- **Console** — the Next.js app. Holds no state; calls the router for everything.
- **Router/orchestrator** — already specced in SCAFFOLD. Reads/writes BigQuery, talks to the three agents.
- **Agents** — the real registered agents across the three clouds (see SETUP.md). The Pipeline view shows *these*.

State lives in **BigQuery** (`mesh`, `evals` datasets), never in a container filesystem — because the loop writes (approvals, eval scores, reroutes) and Cloud Run storage is ephemeral and per-instance.

---

## 2. The Multi-User Problem (Build B only)

If you hand judges a link they run themselves, **shared BigQuery state breaks the demo**: the first judge who clicks Approve and runs the loop changes what the next judge sees. The pipeline shows "already recovered" and the story is gone.

Pick one of three fixes, simplest first:

**Option 1 — Reset button (simplest, recommended).** A visible "Reset demo" control in the console that restores the BigQuery demo tables to their pre-failure seeded state in one click. Each judge resets, runs the loop, sees the full story. Honest and obvious — label it *"Reset to the start of the demo."* A judge resetting a demo is normal and expected; nobody penalises it.

**Option 2 — Per-session namespace.** On first load, the console generates a session ID; all reads/writes are scoped to that session's rows (a `session_id` column in the BigQuery tables, or a per-session dataset). True isolation, more build work, and BigQuery is not ideal for many tiny concurrent write sessions — watch quota.

**Option 3 — Auto-reset on a timer.** A Cloud Scheduler job re-seeds the demo tables every N minutes. Zero UI, but a judge can land mid-reset and see a half-state. Weakest option; use only if you cannot add a button.

**Recommendation: Option 1.** It is a few hours of work, it is honest, and it makes the shared link robust. Build it as part of the console (it is also useful in rehearsal — you will reset constantly).

> Whichever you choose, the loop's write path must be demo-scoped, not global. If Approve writes to the real production golden set with no scoping, the link is single-use. Decide this before you build the console's Approve handler.

---

## 3. Prerequisites

- `SETUP.md` complete: the three clouds provisioned, agents deployed and registered, `mesh` and `evals` BigQuery datasets created.
- BigQuery seeded with the historical routing data — the Pareto view needs history to render a curve. **Seed BigQuery, not SQLite.** (`scripts/seed_demo_data.py`, pointed at BigQuery.)
- The console and router built and passing their VALIDATION checks locally (against BigQuery, `MOCK=false`).
- `gcloud` authenticated, project set, Cloud Run + Cloud Build + Artifact Registry APIs enabled.

---

## 4. Containerizing the Console

A single-purpose Dockerfile for the Next.js app — **no embedded Python**.

```dockerfile
# console/Dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY console/package.json console/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY console/ ./
RUN pnpm build

FROM node:20-slim AS run
WORKDIR /app
RUN corepack enable
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
# Cloud Run injects $PORT (usually 8080). Bind to it — do NOT hardcode 3000.
ENV PORT=8080
EXPOSE 8080
CMD ["pnpm", "start", "--", "-H", "0.0.0.0", "-p", "8080"]
```

Two things people get wrong:
- **Bind `0.0.0.0:$PORT`.** Cloud Run sets `$PORT`; a server bound to `localhost` or hardcoded `3000` fails health checks and the deploy never goes ready.
- **Multi-stage build.** Build with dev dependencies, run with only what is needed — smaller image, faster cold start.

The router has its own Dockerfile per `SCAFFOLD.md`. The agents are already deployed per `SETUP.md`.

---

## 5. Deploying

Build the image explicitly and deploy the digest — more predictable than `gcloud run deploy --source`, which uses Cloud Build from source and is slower and occasionally flaky. You do not want flaky the day before judging.

```bash
source .env.gcp
REPO="us-central1-docker.pkg.dev/${GCP_PROJECT_ID}/agentlab"

# 1. Router/orchestrator first — the console needs its URL.
gcloud builds submit router/ --tag "${REPO}/router:demo"
gcloud run deploy agentlab-router \
  --image "${REPO}/router:demo" \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --min-instances=1 \
  --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID},BQ_DATASET=mesh,MOCK=false" \
  --allow-unauthenticated

ROUTER_URL=$(gcloud run services describe agentlab-router \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --format 'value(status.url)')

# 2. Console second — pointed at the router URL.
gcloud builds submit . --config console/cloudbuild.yaml \
  --substitutions "_TAG=${REPO}/console:demo"
gcloud run deploy agentlab-console \
  --image "${REPO}/console:demo" \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --min-instances=1 \
  --set-env-vars "NEXT_PUBLIC_ROUTER_URL=${ROUTER_URL}" \
  --allow-unauthenticated

gcloud run services describe agentlab-console \
  --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --format 'value(status.url)'
```

Flags that matter:
- **`--min-instances=1`** — kills the cold-start delay. A judge (or you, on stage) clicking a cold URL and waiting 8 seconds for a container to spin up is a bad first impression. SCAFFOLD already calls for this. Costs a few dollars for the event; worth it. Set it back to 0 in TEARDOWN.
- **`--allow-unauthenticated`** — required for a public link judges can open. You are knowingly making it public; there is nothing sensitive in the demo, but do not put real credentials in env vars — use Secret Manager (SETUP.md covers this).
- The router needs the agents' and BigQuery's credentials via its service account, not env-var keys. SETUP.md's IAM section covers the service account; deploy the router with `--service-account` set to it.

---

## 6. Verification

Before you share the link:

- [ ] The console URL loads over HTTPS, no cold-start spinner (min-instances is working).
- [ ] Pipeline view renders the three steps with **live** data from BigQuery — not seed-frozen mock data.
- [ ] Triage view loads; the Approve button is present and interactive.
- [ ] Run the full loop on the deployed URL end to end: trigger → localize → approve → recover. Confirm the recovery **persists** (it wrote to BigQuery, it survives a page reload).
- [ ] **Build B only:** open the link in a second browser / incognito. Confirm either per-session isolation, or that the Reset button restores the start state. Run the loop in one session, confirm the other is unaffected or resettable.
- [ ] Open the link on a phone — judges may. The CONSOLE_DESIGN spec should hold; if it does not, at least confirm it is not broken.
- [ ] Re-run the loop three times on the deployed URL — no flaky hangs (this is VALIDATION §10's repeatability check, against the real deployed thing).

---

## 7. The Fallback Deploy (Build C)

Separately, build the single-container SQLite snapshot — the `node:20-slim` + embedded `agentlab.db` design. It is **not** the main demo, but `FALLBACK.md` explicitly wants a reachable, always-up cached-state version for if the live system breaks on stage. It is legitimate and worth the hour:

- One container, console + a tiny read-only API over the baked-in seeded SQLite DB.
- Deployed to its own Cloud Run service (`agentlab-console-fallback`), its own URL.
- Read-only — it shows a pre-recorded healthy → failed → recovered state; the Approve button can be a no-op that just advances the view.
- **Label it honestly.** If you ever fall back to it, `FALLBACK.md`'s script already tells you how to say so: *"this is from a run an hour ago."* Never present it as live.

Keep the two URLs clearly separate in your own notes so you never paste the fallback link to a judge by mistake.

---

## 8. What to Hand the Judges

If you are sharing a link (Build B), hand it with one line of framing, not bare:

> *"This is AgentLab running live on Cloud Run — the same system from the demo. Hit 'Reset to start' and click through: trigger the failure, watch the triage agent localize it, approve the tests, see the pipeline recover. It's writing to BigQuery in real time across the three clouds."*

That sentence does three things: tells them how to drive it, tells them to reset first, and restates the honest claim — live, real, cross-cloud. A link with no framing gets clicked once and closed; a link with a thirty-second on-ramp gets explored.

---

## 9. Teardown

Add to `TEARDOWN.md` Part 1, or run after the event:

```bash
for svc in agentlab-console agentlab-console-fallback agentlab-router; do
  gcloud run services delete $svc --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID --quiet 2>/dev/null && echo "deleted $svc"
done
```

Also drop `--min-instances` to 0 if you keep any service alive, so it does not bill while idle.

---

## Summary

- **Main demo and shared link** are BigQuery-backed, multi-service (console + router + the three real agents). Not SQLite.
- **Separate Cloud Run services**, console calls router by URL — never one container with two processes.
- **The shared link needs a Reset button** (Option 1 in §2) so each judge sees the full story.
- **`--min-instances=1`** during the event; bind `0.0.0.0:$PORT`; build the image explicitly.
- **Build the SQLite single-container version too** — but as the labelled `FALLBACK.md` asset, never as the main demo.
- The main demo's job is to be *true*. Deploy the thing your pitch describes.

# AgentLab

**When a multi-agent pipeline produces a confident wrong answer — which step broke, and how do you know?**

AgentLab is an evaluation system for multi-step agent pipelines. It watches production traces, detects quality drift, and does the part nobody else automates: it **localizes the regression to the specific step that caused it**. From the real failing traces it drafts targeted evaluation cases; a human approves them; the fleet is re-scored against the enlarged suite; the degraded step is rerouted to a healthy agent.

Built on Gemini 3.5 Flash. The demo pipeline genuinely spans three clouds — but, deliberately, none of the claims below depend on that.

---

> **Built for the post-I/O '26 Gemini hackathon.** The headline is **step-level fault localization** — credit assignment in a multi-agent pipeline, attributing a downstream wrong answer to the upstream step responsible. The loop around it — detect → localize → generate evals → *human approves* → re-score → reroute — is how that localization becomes a measurable repair, live, inside a three-minute demo.

---

## The Hard Problem: Which Step Broke?

A multi-step agent pipeline returns a bad answer. Three steps touched it — in a larger system, forty. Which one caused the regression?

This is a **credit-assignment problem**, and it is not solved. The agent that emits the visibly-wrong output is frequently not the one that broke: a quietly degraded *upstream* step hands plausible-but-wrong intermediate state to a healthy *downstream* step, which faithfully turns it into a wrong final answer. Blaming the last agent is blaming the messenger.

Every agent-observability product shipped in 2026 — Gemini Enterprise, AWS AgentCore, the rest — shows you *what each agent did*: traces, spans, token counts, latency. None of them tell you *which agent is responsible* for a drop in output quality. That attribution is left to a human reading traces at 2 a.m.

AgentLab's core is that attribution: given production traces of a multi-step pipeline and a measured drop in quality, **localize the drop to a specific step, with statistical evidence rather than a guess.** Everything else in the system — the signal layer, the eval loop, the router — exists to make that localization continuous and to act on it.

## How Localization Works

Localization is only as good as the evidence under it. AgentLab builds that evidence in three layers:

1. **Per-step signals, one schema.** Every step emits explicit signals (tool-error rate, latency, cost, handoff-failure rate) and cheap implicit signals (small classifiers + regex). Signals from every step — and every cloud — normalize to a single OpenTelemetry schema. That normalization is what makes one step comparable to another, which is what makes localization possible.

2. **Step-local oracles where they exist.** Some steps have a cheap source of ground truth. The causal-estimation step does: an effect estimate outside statistically plausible bounds is *provably* wrong, with no LLM judge needed. Where such an oracle exists, localization there is near-certain. Where it doesn't, localization leans on signal drift and clustering — weaker, and the README is honest about that asymmetry (see *Honest Gaps*).

3. **Cluster, then pin.** The triage agent (Gemini 3.5 Flash) pulls a window of recent traces, embeds and clusters the failures, and pins each cluster to the step and pipeline position where it originated — distinguishing the step that *broke* from the steps that merely *propagated* the bad state downstream.

The output is not "something is wrong." It is "step 2 regressed; here is the cluster of traces; here is the statistical confirmation; here is the one-line root cause."

## The Loop: Localization Becomes Repair

Localization is the hard part. The loop is what turns it into an action you can measure:

1. **Detect** — signal drift fires on a step (online CUSUM/EWMA control charts).
2. **Localize** — the triage agent clusters the failures and pins each to its step.
3. **Generate** — for each localized failure, the triage agent drafts 3–5 new evaluation tasks targeting that exact failure mode, written from the real traces.
4. **Approve** — a human reviews the drafted tasks and approves (see next section — this gate is deliberate).
5. **Re-score** — approved tasks enter the golden set; the fleet is re-evaluated against the enlarged suite.
6. **Reroute** — the router reads the new scores and routes the degraded step to a healthy agent on its next run.

The result the demo shows: a localized failure, new tests written from it, and a **measured quality number recovering** — end to end, in about ninety seconds.

## Why a Human Approves the Generated Tests — On Purpose

The triage agent *drafts* new eval cases. It does not commit them. A person approves them before they enter the golden set.

This is a deliberate design decision, not an unfinished feature. The eval set governs routing — it is the system's definition of "quality." If an LLM could silently rewrite the suite that judges quality, it would amplify its own errors with no external check: a triage agent that mis-clusters would generate skewed tests, which would mis-score the fleet, which would mis-route. The loop is **supervised by design.** AgentLab is a copilot for eval-set maintenance, not an unsupervised self-modifying system — and that boundary is a feature.

What *is* automatic: detection, localization, test drafting, re-scoring, and rerouting once tests are approved. What is not, and should not be: letting the system rewrite its own definition of correctness unattended.

## Why This, Why Now

**The harness now matters more than the model.** SWE-Bench Pro shows 22-point swings on identical model weights from scaffold-only changes; OpenAI stopped reporting SWE-Bench Verified scores in February 2026 citing 12-point harness inflation. The differentiator in production agents is no longer which model — it is how well the surrounding system evaluates, localizes failures, and adapts.

**Model upgrades now happen under you.** Agent runtimes auto-upgrade. When a step in your pipeline is run by an outside vendor, *their* upgrade silently changes *your* output — you did not choose it and were not told. A static eval suite written at T0 goes stale the moment reality moves past it.

**A wrong answer that looks right is the real danger.** A crashed agent is obvious. A causal-estimation agent that quietly starts producing effect estimates outside its true confidence bounds is not — it ships a confident wrong number straight into a launch decision. Catching *subtle, plausible* degradation, and attributing it correctly, is the hard problem.

**Gemini 3.5 Flash makes continuous triage affordable.** The triage agent runs on every window of traces — clustering, localizing, drafting tests. That only pencils out as always-on infrastructure with a model fast and cheap enough to run that way: frontier-level agentic reasoning at Flash cost and Flash speed.

## What AgentLab Is

Four components. The first three are the loop; the fourth is the surface you watch it on.

### 1. The Signal Layer — *cheap, continuous, every trace*
At production volume, judging every agent output with an LLM is too expensive and too slow. Two tiers:
- **Explicit signals** (deterministic, free): tool-error rate, latency p50/p95, cost per call, handoff-failure rate between steps.
- **Implicit signals** (cheap, ~$0.00002/trace): regex patterns plus four small DistilBERT binary classifiers — refusal, task-failure, low-confidence-output, malformed-handoff — co-hosted CPU-side, three orders of magnitude cheaper than an LLM judge.
- **Out-of-bounds detection**: for the causal step specifically, a check that flags effect estimates outside statistically plausible bounds — the step-local oracle, and the "confident wrong number" detector.
- **Self-report**: every agent carries a `report(reason)` tool, named neutrally so models actually use it.

All signals normalize to a single OpenTelemetry schema — the contract that makes cross-step (and cross-cloud) localization possible.

### 2. The Triage Agent — *the localization engine*
A Gemini 3.5 Flash agent that runs continuously:
1. Pulls the last window of production traces across the pipeline.
2. Embeds and clusters them — finds the recurring failure shapes.
3. **Localizes** each bad cluster to a specific pipeline step, separating the step that broke from steps that propagated the failure.
4. For each, writes a one-line root cause and **3–5 new evaluation tasks** targeting that exact failure.
5. Surfaces them for human approval.
6. On approval, the new tasks enter the golden set and re-score the fleet.

Step 3 is the crown jewel — and the part nobody else has automated.

### 3. The Router — *acts on what the loop learns*
Given a pipeline step and the agents that can perform it, the router picks the best by quality × cost × latency.
- **Baseline** (`embed-and-match`): cosine-match the step to agent capability descriptors; cost-weighted argmax.
- **Learned router**: a LightGBM model predicting `P(success | step, agent)` from step embedding, agent capability, recent eval scores, signal rates, cost, and latency.
- **Bandit cold-start**: LinUCB exploration for newly-registered agents.
- When the loop re-scores a step's agent downward, the router reroutes that step on the next run.

The router is the *actuator*, not the claim — routing is well-trodden (RouteLLM, FrugalGPT). What is novel is what drives it: a localized, freshly-generated notion of quality.

### 4. The Console — *where you watch the loop run*
A React + Tailwind dashboard. Five views: **Pipeline** (the workflow, live, each step's health), **Router** (live decision feed with explanations), **Signals** (signal rates, cluster drill-down), **Triage** (localized failure clusters, proposed tests, Approve button), **Pareto** (the cost-vs-quality chart).

## The Pipeline Spans Three Clouds — And Why That's Not the Headline

AgentLab's demo workflow is a real task every product data-science team will recognize — **automated analysis of a concluded A/B experiment** — run as three specialist agents:

| Step | Agent | Cloud | Why this cloud |
|------|-------|-------|----------------|
| 1. Data prep & validation | Pulls event data, checks sample-ratio mismatch, validates randomization | **GCP** (Gemini Enterprise + BigQuery) | Data gravity — step 1 runs where the warehouse already is. |
| 2. Causal estimation | Treatment effect, CUPED, heterogeneous effects, quasi-experimental correction | **AWS** (AgentCore) | An **external experimentation vendor** — a Statsig/Eppo-class specialist — runs it, and they run on AWS. |
| 3. Readout & recommendation | Drafts the stakeholder-ready "ship / don't ship / iterate" memo | **Azure** (Azure OpenAI) | A Microsoft 365 shop; the readout is consumed where PMs and execs work. |

It is genuinely multi-cloud — three steps owned by three parties, an architecture you inherit rather than design, and one you cannot "just consolidate" because step 2 is not yours to move. The agents perform real A2A handoffs across the cloud boundary.

**But it is deliberately not the headline.** The localization claim — *which step broke, and how do you know* — holds identically whether the pipeline runs on one cloud or three, because localization operates at the *step* level. Cross-cloud makes the demo realistic and the threat model honest (a vendor's silent upgrade on a cloud you don't control). It is a feature of the setting, not the novel contribution. Google shipped cross-cloud *infrastructure* at Next '26 — data federation, networking, traffic observability. AgentLab does not compete with any of it and does not need to.

## Managed Agents Integration

AgentLab integrates managed agent platforms at the registry and execution layers:
- **Registry Layer (Google Cloud Agent Platform)**: All step-agents (GCP, AWS, Azure OpenAI) are cataloged in Google Cloud's canonical registry (via `gcloud agent-platform registry agents register`) to expose their routing metadata and capabilities.
- **AWS Bedrock Managed Runtime (Step 2)**: The causal estimation agent directly invokes an AWS Bedrock Managed Agent runtime (`boto3.client('bedrock-agentcore-runtime')` with `invoke_agent`) when `MOCK=false`.
- **Custom Wrapper Fallback (Steps 1 & 3)**: The data-prep and readout agents use custom container services wrapping the models (configured with Google's `adk_config.yaml`). This design allows rich database tool calling (e.g. querying GCP BigQuery), bypassing the skills-in-Markdown constraint of the early GCP Managed Agents API.

## Pre-Registered Hypotheses

Thresholds set in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) *before* any data was collected. The eval rigor here is deliberate — it is how a quality claim becomes a measured result instead of a demo assertion.

- **H1**: The learned router strictly Pareto-dominates the embed-and-match baseline across all task families.
- **H2**: Cheap classifiers detect ≥80% of failures an LLM judge would flag, at ≤0.1% of the cost.
- **H3**: Triage-generated eval tasks overlap meaningfully with what a human DS would have written, by manual review of 30 sampled clusters.
- **H4**: A model upgrade is localized to the correct step by online signal drift within 30 minutes, false-positive rate under 5%.
- **H5**: After the loop runs, the degraded step's measured quality recovers by a statistically significant margin.

A failed hypothesis gets honest treatment in the writeup, not concealment.

## Architecture

```
                  ┌─────────────────────────────────┐
                  │       ORCHESTRATOR (hub)        │
                  │   router decides each step's    │
                  │   agent; A2A handoffs           │
                  └───┬───────────┬───────────┬─────┘
                      │ A2A       │ A2A       │ A2A
                ┌─────▼────┐ ┌────▼─────┐ ┌───▼──────┐
                │ STEP 1   │ │ STEP 2   │ │ STEP 3   │
                │ data prep│ │ causal   │ │ readout  │
                │ GCP      │ │ AWS      │ │ Azure    │
                └─────┬────┘ └────┬─────┘ └───┬──────┘
                      │           │           │
                      └─────── traces ────────┘
                                  │
        ┌──────────── The Loop ▼──────────────────┐
        │  SIGNAL LAYER → TRIAGE (localize the     │
        │  failed step + draft tests) → HUMAN      │
        │  APPROVES → EVAL HARNESS (re-score) →    │
        │  ROUTER (reroute the failed step) ───────┘
        │                                          │
        └──── back into the orchestrator's next run ┘

   surfaced in: the Console (Pipeline · Router · Signals · Triage · Pareto)
```

## Project Structure

```
agentlab/
├── README.md  SETUP.md  SCAFFOLD.md  FALLBACK.md
├── VALIDATION.md       # end-to-end test & validation checklist
├── common/             # schema (the contract layer), config, otel, bq
├── orchestrator/       # hub agent, A2A handoff, embeds the router
├── agents/             # data_prep (GCP), causal_estimation (AWS),
│                       #   readout (Azure), + spare agents for reroute
├── mesh/               # cross-cloud adapters + canonical registry
├── router/             # baseline, learned, bandit, cascade
├── signals/            # explicit, regex, classifiers, oob_detector, self_report
├── triage/             # cluster, localize, generate_tasks, surface, runner
├── sentry/             # offline_regression, online_cusum
├── harness/            # tasks (golden sets), scorers, inspect_runner
├── console/            # Next.js + React + Tailwind dashboard
├── infra/              # terraform per cloud, docker
├── scripts/            # seed_demo_data, smoke_test
└── docs/               # METHODOLOGY, DEMO, ARCHITECTURE
```

Build order is in [`SCAFFOLD.md`](SCAFFOLD.md). Cloud setup is in [`SETUP.md`](SETUP.md). If something breaks on demo day, [`FALLBACK.md`](FALLBACK.md) has the collapse plan.

## License

MIT.

## Contact

Apoorv Shrivastava — Senior Data Scientist, Bay Area.
[LinkedIn](https://www.linkedin.com/in/apoorv-shrivastava/) · [GitHub](https://github.com/apoorv-shrivastav)

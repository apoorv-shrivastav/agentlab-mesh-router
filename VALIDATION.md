# VALIDATION.md — Testing & Validation Checklist

How to confirm everything works as expected. Walk this top to bottom; each section has explicit pass criteria. If a check fails, fix it before moving on — later checks assume earlier ones passed.

The checks are ordered to match the build: contracts → components → integration → the loop → the demo. The single most important section is **§7, The Loop**, because the loop is the project — a green light there is what matters most.

> **How to read a check.** Each is a concrete action with a **PASS** condition. "PASS: …" means that exact observable result. If you get anything else, it's a fail — note it and fix before continuing.

---

## §0 — Environment Preconditions

- [ ] `python --version` → 3.11 or higher. **PASS**: 3.11+.
- [ ] `node --version` → 20 or higher. **PASS**: 20+.
- [ ] `docker ps` runs without error. **PASS**: Docker daemon responds.
- [ ] `.env.gcp`, `.env.aws`, `.env.azure` exist and are populated. **PASS**: all three present, no empty required values.
- [ ] `gcloud auth print-access-token` returns a token. **PASS**: a token prints.
- [ ] `aws sts get-caller-identity` returns an identity. **PASS**: account/ARN prints.
- [ ] `az account show` returns a subscription. **PASS**: subscription prints.
- [ ] No secret values are committed: `git grep -iE "xoxb-|sk-|AKIA|BEGIN PRIVATE" $(git rev-list --all)` finds nothing. **PASS**: no matches.

---

## §1 — Contracts (`common/schema.py`)

- [ ] `python -c "from common.schema import AgentDescriptor, AgentRequest, AgentResponse, RouteDecision, Signal, EvalScore, TriageCluster"` runs clean. **PASS**: no import error.
- [ ] Every Pydantic model instantiates with valid data and rejects invalid data (a quick `pytest tests/test_schema.py`). **PASS**: valid cases construct, invalid cases raise `ValidationError`.
- [ ] `git log --oneline -- common/schema.py` shows no changes after the Milestone 0 sign-off commit. **PASS**: schema frozen since sign-off (or any change has an explicit sign-off commit message).

---

## §2 — The Workflow Agents (MOCK mode)

Run with `MOCK=true`.

- [ ] `pytest tests/test_agents.py` passes. **PASS**: all workflow agents accept an `AgentRequest`, return a valid `AgentResponse`.
- [ ] Each agent's `descriptor` returns a well-formed `AgentDescriptor` with a real `platform` and `task_families`. **PASS**: five valid descriptors, distinct `agent_id`s.
- [ ] Each agent exposes the `report(reason)` self-diagnostic tool. **PASS**: `report` is in every agent's tool list.
- [ ] Token counts and latency in mock responses are plausible, not zeros or constants. **PASS**: values vary and look realistic.

---

## §3 — Harness & Scorers

- [ ] `make seed` populates the local mock store. **PASS**: store exists, contains responses / signals / eval scores for all agents.
- [ ] `pytest tests/test_harness.py` passes. **PASS**: running the harness on a seeded agent yields `EvalScore`s.
- [ ] Each `EvalScore` has a `pass_k`, an `n_trials`, and a confidence interval with `ci_low <= pass_k <= ci_high`. **PASS**: CIs are well-ordered and non-degenerate.
- [ ] The tool-call scorer (`scorers/tool_call.py`) correctly accepts a known-good tool call and rejects a malformed one. **PASS**: both cases correct.
- [ ] The judge scorer's bias controls are active: answer order is randomized, and a separate judge model family is used. **PASS**: confirmed in code and in a test run.

---

## §4 — Signal Layer

- [ ] `pytest tests/test_signals.py` passes. **PASS**: all signal tests green.
- [ ] The four classifiers load and return a binary label + score on sample inputs. **PASS**: refusal, task-failure, low-confidence-output, malformed-handoff each classify.
- [ ] Regex failure patterns fire on known phrases and not on neutral text. **PASS**: true positives fire, neutral text does not.
- [ ] Classifier inference latency is well under one second CPU-side. **PASS**: < ~200ms per inference.
- [ ] A seeded `report()` call surfaces as a `self_report` signal. **PASS**: self-report appears in the signal stream.
- [ ] **Cost check (hypothesis H2)**: classifier cost per trace is ≤0.1% of an LLM-judge call on the same trace. **PASS**: measured ratio ≤ 0.001.

---

## §5 — Router

- [ ] `pytest tests/test_router.py` passes. **PASS**: all router tests green.
- [ ] The baseline `embed-and-match` router returns a valid `RouteDecision` with a non-empty `explanation`. **PASS**: valid decision, human-readable explanation.
- [ ] The learned router returns a valid `RouteDecision` and its `candidates` list is populated with per-agent predicted quality and cost. **PASS**: candidates present and sensible.
- [ ] The bandit explores: a newly-registered agent with <20 calls receives exploratory traffic. **PASS**: cold-start agent gets routed to at least once within the first 20 requests.
- [ ] Routing decision overhead is sub-second. **PASS**: p50 decision latency < 1s.
- [ ] **Pareto check (hypothesis H1)**: on seeded data, the learned router's cost-quality curve is at or above the baseline's at every cost point. **PASS**: learned curve dominates; no crossover.

> If H1 fails on seeded data, the problem is the seed data or the feature pipeline — not the router algorithm. Fix the seed data so quality differences between agents are real and learnable, then re-check.

---

## §6 — Drift Sentry

- [ ] `pytest tests/test_sentry.py` passes. **PASS**: all sentry tests green.
- [ ] Inject a known regression into seeded data → the offline McNemar check flags it. **PASS**: regression detected.
- [ ] Feed pure noise (no real regression) → the offline check does **not** flag it. **PASS**: no false positive.
- [ ] The online CUSUM chart fires within the expected window on an injected signal-rate shift. **PASS**: fires, and within ~30 simulated minutes.
- [ ] Benjamini-Hochberg correction is applied across task families. **PASS**: confirmed in code; flagging is not per-family-uncorrected.
- [ ] **Hypothesis H4**: a simulated model upgrade is caught by online drift within 30 minutes with a false-positive rate under 5% across repeated trials. **PASS**: detection + FP rate both within target.

---

## §7 — THE LOOP (most important section)

This is the project. Everything above is in service of this. Run the full loop end to end and confirm every link.

The headline claim under test: the triage agent localizes the failure to the step that **caused** it, and does **not** mis-blame the downstream step that merely propagated it. The §7 gate must prove that specifically — a loop that "detects something wrong" but blames the wrong step fails this section.

- [ ] **Trigger**: degrade the AWS causal-estimation step via model swap — and leave the Azure readout agent's own model untouched. **PASS**: the causal agent produces an out-of-bounds effect estimate; the readout agent, fed that bad estimate, produces a confident wrong recommendation *while its own model is unchanged* — the symptom is downstream, the fault is upstream.
- [ ] **Detect**: the signal layer registers the drift. **PASS**: the out-of-bounds detector fires on the causal step; the readout step also shows degraded output quality — both signals elevate, the system sees a problem.
- [ ] **Cluster**: the triage agent pulls recent traces across the pipeline and clusters the failures. **PASS**: the bad traces group coherently, not scattered.
- [ ] **Localize — the headline check**: the triage agent attributes the regression to the **causal step (the cause)** and identifies the **readout step as a downstream symptom**, not as an independent fault. **PASS**: `cause_step == causal_estimation`; `readout` appears in `symptom_steps`, not as a second cause. **FAIL if** the triage agent blames the readout step — that is mistaking symptom for cause, and it is the exact failure the project claims to solve.
- [ ] **Diagnose**: the triage agent produces a one-line root cause. **PASS**: it is specific and plausibly correct — names the causal step's degradation and the propagation, not a generic "quality dropped."
- [ ] **Generate**: the triage agent emits 3–5 new eval tasks targeting the causal-step failure. **PASS**: new tasks exist, well-formed, clearly about the observed failure mode.
- [ ] **Approve**: the human approval action adds the new tasks to the golden set. **PASS**: golden set grows by the approved count; approval is an explicit human action, not automatic.
- [ ] **Re-score**: the fleet is re-evaluated against the enlarged golden set. **PASS**: the degraded causal agent now has a lower `EvalScore` on the `causal_estimation` family.
- [ ] **Reroute**: the router, reading the new scores, reroutes the causal step to a healthy agent. **PASS**: post-loop, the causal step runs on a different agent.
- [ ] **Recover**: the pipeline's measured quality improves. **PASS**: the causal estimate is back within plausible bounds — and the readout's recommendation is correct again *because its input is now correct*, confirming the symptom resolved once the cause was fixed.
- [ ] **Hypothesis H5**: the recovery is statistically significant, not noise. **PASS**: the before/after delta clears the pre-registered threshold with a CI excluding zero.

**The loop passes only if every link above is green — and the Localize check in particular.** A loop that recovers the pipeline but blamed the wrong step has not demonstrated the headline. This section is the gate.

- [ ] **Timing**: the full loop, from trigger to visible recovery of the pipeline, completes in about 90 seconds. **PASS**: ≤ ~120 seconds end to end.
- [ ] **Repeatability**: run the loop three times. **PASS**: it completes cleanly all three times, and localizes to the causal step all three times — no flaky hangs, no flaky attribution.

---

## §8 — Cross-Cloud Federation

- [ ] All workflow agents (the three steps plus spares) appear in the federated registry, each tagged with its real platform. **PASS**: all agents present, correct `platform` on each.
- [ ] The GCP adapter pulls real signals from a GCP-hosted agent. **PASS**: real GCP telemetry in the federated store.
- [ ] The AWS adapter pulls real signals from the AgentCore agent. **PASS**: real CloudWatch-sourced telemetry, normalized to the canonical schema.
- [ ] The Azure adapter pulls real signals from the Azure OpenAI agent via Application Insights. **PASS**: real Azure telemetry, normalized.
- [ ] Signals from all three clouds share one schema in BigQuery. **PASS**: a single query returns rows from all three platforms with consistent columns.
- [ ] A request can route to an agent on each of the three clouds and return a real response. **PASS**: one successful real round-trip per cloud.

> If cross-cloud is degraded, this section can fail without killing the demo — see FALLBACK.md. The loop (§7) is the gate; cross-cloud (§8) is upside.

---

## §9 — The Console

- [ ] The console builds and serves. **PASS**: `pnpm build` succeeds, the app loads.
- [ ] **Pipeline view**: shows the cross-cloud workflow and all agents with live quality / cost / latency. **PASS**: renders, data is live.
- [ ] **Router view**: live decision feed updates as requests route. **PASS**: decisions stream in with explanations.
- [ ] **Signals view**: signal rates render; clusters drill down. **PASS**: rates shown, drill-down works.
- [ ] **Triage view**: failure clusters, proposed tasks, working Approve button. **PASS**: clusters render, Approve fires the loop.
- [ ] **Pareto view**: the four-curve chart renders with real data. **PASS**: chart renders, learned curve visibly dominates.
- [ ] No console errors in the browser devtools during a full demo run. **PASS**: clean console.
- [ ] The console is responsive at the resolution you'll present on. **PASS**: looks right on the demo screen/projector.

---

## §10 — The Full Demo Dry-Run

The final gate before judging. Run the entire 3-minute demo from PITCH.md, start to finish, on the real system.

- [ ] The demo completes at the target time. **PASS**: lands at ~3:00, ≤ 3:15 ceiling.
- [ ] Every beat (pipeline → drift → localize → recover → chart) lands as scripted. **PASS**: all five beats work live.
- [ ] The headline number (the causal estimate returning within plausible bounds, or your real figures) visibly moves. **PASS**: the number changes on screen.
- [ ] Run the dry-run **three times**. **PASS**: all three complete cleanly with no hangs.
- [ ] Time each beat; none overruns its budget. **PASS**: beat timings within the PITCH.md budget.
- [ ] The FALLBACK.md plan is staged: pre-run loop result saved, recording captured, cached state ready. **PASS**: fallback assets exist and are reachable offline.
- [ ] The repo is public and the README clearly states what the project is. **PASS**: public repo, accurate README.

---

## §11 — Pre-Judging Final Checks

- [ ] `docs/METHODOLOGY.md` exists, is committed, and its hypothesis thresholds were set before data collection. **PASS**: present, timestamped before the data.
- [ ] Every headline number in PITCH.md matches what the system actually produces. **PASS**: pitch numbers == real numbers.
- [ ] The "what is NOT built" section in the README is accurate and current. **PASS**: honest gaps list matches reality.
- [ ] You can answer each hard question in PITCH.md §Q&A out loud, smoothly. **PASS**: rehearsed, no fumbling.
- [ ] Laptop charged, screen-share tested, backup recording on the laptop offline. **PASS**: all logistics confirmed.

---

## Validation Summary Gate

Before judging, the minimum bar:

| Section            | Required? | If it fails                                 |
|--------------------|-----------|----------------------------------------------|
| §0–§6 components   | Yes       | Fix before demo — these underpin the loop    |
| **§7 The Loop**    | **Yes — the gate** | No demo without it; fix or trigger FALLBACK |
| §8 Cross-cloud     | No        | Degrade to fewer clouds per FALLBACK.md      |
| §9 Console         | Mostly    | Pipeline/Triage/Pareto required; others can be described |
| §10 Demo dry-run   | Yes       | Do not present an un-rehearsed demo          |
| §11 Final checks   | Yes       | Quick; no reason to skip                     |

When §7 is fully green and §10 has had three clean runs, you are ready. Everything else is upside.

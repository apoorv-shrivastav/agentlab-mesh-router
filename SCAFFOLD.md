# SCAFFOLD.md — Build-Order Spec for the AgentLab Codebase

This document tells a coding agent (Claude Code or equivalent) **exactly what to build, in what order, with what interface contracts**. It exists because `SETUP.md` assumes a codebase that does not yet exist — every deferred cloud step is blocked on agent containers and service code that has to be written first.

**How to use this document.** Hand the coding agent four files: `README.md` (the architecture and component specs), this file (`SCAFFOLD.md`, the build order and contracts), `SETUP.md` (the infra it must be compatible with), and `CONSOLE_DESIGN.md` (the visual spec for Milestone 8). Tell it: *"Work through SCAFFOLD.md milestone by milestone. Do not skip ahead. Stop at each checkpoint and let me verify before continuing."*

> **Naming.** The product is **AgentLab**. Internal infrastructure resource names use the `mesh-` prefix (`mesh-router`, `mesh-causal-agent`, the `mesh` BigQuery dataset, `MESH_ROUTER_URL`, etc.) — this is the infra-layer name, kept stable because real cloud resources in `SETUP.md` already carry it. Treat `mesh-*` as the infrastructure namespace and **AgentLab** as the product; do not rename infra resources to chase consistency. Anything user-facing — the console, the README, the pitch — says AgentLab.

**Golden rules for the coding agent** (repeat these in the prompt):
1. Build in milestone order. Each milestone has a checkpoint; stop there.
2. Every module exposes the interface defined here. Do not invent alternative signatures — other modules depend on these contracts.
3. Mock external clouds until Milestone 7. Use a `MOCK=true` env flag everywhere so the system runs end-to-end with zero cloud credentials during early development.
4. New I/O '26 APIs (Managed Agents, AgentCore `bedrock-agentcore-control`) are recent — if unsure of an API surface, write the call behind an interface and a mock, and flag it for the human to verify against current docs. Do not guess silently. **Known constraint: as of I/O '26, the Managed Agents API ships skills-in-Markdown only — MCP / tool-calling is on the roadmap but not yet available. Before committing any step-agent that needs rich tool use to Managed Agents, the human must verify current tool-calling support. If it is not yet available, the fallback is ADK + Agent Runtime. Resolve this BEFORE the build rehearsal, not at Milestone 7.**
5. Prefer small, runnable increments. After every milestone the repo must `make test` clean.
6. Never hardcode credentials, project IDs, ARNs. Everything comes from env / `.env.*` files (already gitignored per SETUP.md).

---

## Target Repository Layout

This is the structure to create. It matches the "Project Structure" section of `README.md`.

```
agentlab-mesh-router/
├── README.md  SETUP.md  SCAFFOLD.md  FALLBACK.md   # docs (already exist)
├── PITCH.md  VALIDATION.md  TEARDOWN.md             # docs (already exist)
├── Makefile                                        # test, lint, run, deploy targets
├── pyproject.toml                                  # Python deps, tooling config
├── .env.example                                    # template; real .env.* are gitignored
├── pnpm-workspace.yaml                             # for the console
├── docker-compose.yml                              # local all-in-one for dev
├── common/
│   ├── schema.py            # canonical data models (THE contract layer)
│   ├── config.py            # env loading, MOCK flag, cloud config
│   ├── otel.py              # OpenTelemetry span helpers
│   └── bq.py                # BigQuery read/write helpers (mockable)
├── orchestrator/
│   ├── hub.py               # drives the workflow; embeds the router
│   └── a2a.py               # A2A handoff between steps (sequential fallback inside)
├── agents/
│   ├── base/agent_iface.py  # the Agent interface every agent implements
│   ├── data_prep/           # step 1 — GCP
│   ├── causal_estimation/   # step 2 — AWS
│   ├── readout/             # step 3 — Azure
│   └── spares/              # healthy alternates the router can reroute to
├── mesh/
│   ├── adapters/{base,gcp,aws,azure}.py
│   ├── registry.py
│   └── schema.py            # re-exports from common/schema.py
├── router/
│   ├── baseline_embed_match.py
│   ├── learned_router.py
│   ├── bandit.py
│   ├── cascade.py
│   ├── features.py
│   └── server.py            # FastAPI app, Cloud Run entrypoint
├── signals/
│   ├── explicit/collectors.py
│   ├── regex/patterns.py
│   ├── classifiers/{model.py,train.py,infer.py}
│   └── self_report_tool.py
├── triage/
│   ├── cluster.py
│   ├── localize.py          # cause-vs-symptom step attribution — the crown jewel
│   ├── generate_tasks.py
│   ├── a2ui_surface.py
│   └── runner.py            # Cloud Run job entrypoint
├── sentry/
│   ├── offline_regression.py
│   └── online_cusum.py
├── harness/
│   ├── tasks/               # golden-set YAML, one file per task family
│   ├── scorers/{tool_call.py,end_state.py,judge.py}
│   └── inspect_runner.py
├── console/                 # Next.js + React + Tailwind + shadcn/ui
│   ├── app/{pipeline,triage,signals,router,pareto}/
│   ├── components/
│   └── lib/api.ts
├── infra/
│   ├── terraform/{gcp,aws,azure}/
│   └── docker/              # one Dockerfile per deployable service
├── scripts/
│   ├── seed_demo_data.py    # generates realistic mock traffic + eval logs
│   └── smoke_test.py        # end-to-end check
├── tests/
└── docs/
    ├── METHODOLOGY.md
    ├── DEMO.md
    └── ARCHITECTURE.md
```

---

## The Contract Layer — `common/schema.py`

**Build this first and freeze it.** Every other module imports these. If these change later, everything breaks. Use Pydantic models.

```python
# common/schema.py — canonical data models. THE interface contract.

from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class Platform(str, Enum):
    GCP_ADK = "gcp_adk"
    GCP_MANAGED = "gcp_managed"
    AWS_AGENTCORE = "aws_agentcore"
    AZURE_OPENAI = "azure_openai"

class TaskFamily(str, Enum):
    DATA_PREP = "data_prep"          # step 1: pull, SRM check, validate randomization
    CAUSAL_ESTIMATION = "causal_estimation"  # step 2: effect, CUPED, hetero effects
    READOUT = "readout"              # step 3: stakeholder ship/no-ship memo

class AgentDescriptor(BaseModel):
    agent_id: str
    display_name: str
    platform: Platform
    task_families: list[TaskFamily]
    capability_text: str          # natural-language description; gets embedded
    cost_per_1k_tokens: float
    endpoint: str | None = None
    external_id: str | None = None

class AgentRequest(BaseModel):
    request_id: str
    prompt: str
    task_family: TaskFamily | None = None   # None => router infers
    attachments: list[str] = []

class AgentResponse(BaseModel):
    request_id: str
    agent_id: str
    output: str
    success: bool | None = None   # filled by scorer, not the agent
    tokens_in: int
    tokens_out: int
    latency_ms: float
    tool_calls: list[dict] = []
    self_reports: list[str] = []  # from the report() tool

class RouteDecision(BaseModel):
    request_id: str
    chosen_agent_id: str
    router_kind: str              # "baseline" | "learned" | "bandit"
    score: float
    explanation: str              # human-readable, shown in the console
    candidates: list[dict]        # [{agent_id, score, predicted_cost, predicted_quality}]
    decision_latency_ms: float

class Signal(BaseModel):
    request_id: str
    agent_id: str
    timestamp: datetime
    kind: str                     # "refusal"|"task_failure"|"low_confidence_output"|"malformed_handoff"|"out_of_bounds"|"tool_error"|"latency"|"cost"|"self_report"
    value: float                  # 1.0/0.0 for binary, raw value for explicit
    source: str                   # "regex"|"classifier"|"explicit"|"self_report"

class EvalScore(BaseModel):
    agent_id: str
    task_family: TaskFamily
    pass_k: float                 # pass^k consistency
    n_trials: int
    ci_low: float
    ci_high: float
    timestamp: datetime

class TriageCluster(BaseModel):
    cluster_id: str
    size: int
    cause_step: TaskFamily        # the step that BROKE — localization output
    cause_agent_id: str           # the agent on the cause step
    symptom_steps: list[TaskFamily] = []  # downstream steps that propagated the failure
    localization_basis: str       # how the cause was attributed (oracle | signal drift | trace order)
    root_cause: str               # one-line, LLM-generated
    proposed_tasks: list[dict]    # [{prompt, task_family, expected}]
    status: str                   # "proposed"|"approved"|"rejected"
```

The agent must treat this file as immutable after Milestone 0 review. Any change requires explicit human sign-off.

---

## Milestones

Each milestone is independently runnable and testable. The order is dependency-correct: nothing references a thing not yet built.

### Milestone 0 — Skeleton + Contracts
*Goal: repo exists, contracts frozen, `make test` runs (trivially).*

- Create the full directory tree above with empty `__init__.py` / placeholder files.
- Write `common/schema.py` exactly as specified.
- Write `common/config.py`: loads `.env.gcp/.env.aws/.env.azure`, exposes a `MOCK` boolean (default `True`), exposes typed config objects.
- Write `pyproject.toml` with deps: `pydantic`, `fastapi`, `uvicorn`, `lightgbm`, `scikit-learn`, `numpy`, `scipy`, `pandas`, `google-cloud-bigquery`, `google-cloud-aiplatform`, `boto3`, `openai` (for the Azure OpenAI agent), `azure-monitor-query`, `azure-identity`, `inspect-ai`, `hdbscan`, `umap-learn`, `transformers`, `torch` (CPU), `pytest`, `ruff`.
- Write `Makefile`: `test`, `lint`, `run-router`, `run-console`, `seed`, `smoke`.
- Write `.env.example` with every variable named in SETUP.md.

**Checkpoint**: `make test` passes (no tests yet, exits clean). `python -c "from common.schema import AgentDescriptor"` works. Human reviews `schema.py` and signs off. **Stop here.**

### Milestone 1 — The Workflow Agents + Orchestrator (mockable)
*Goal: three step-agents plus spares and a hub orchestrator, each satisfying the Agent interface, running in MOCK mode with no cloud.*

- `agents/base/agent_iface.py` — abstract base:
  ```python
  class Agent(ABC):
      descriptor: AgentDescriptor
      @abstractmethod
      def handle(self, req: AgentRequest) -> AgentResponse: ...
  ```
- The three step-agents — `data_prep` (GCP), `causal_estimation` (AWS), `readout` (Azure) — plus 2–3 `spares/` (healthy alternates the router can reroute a degraded step to). Each agent folder gets: an implementation, a `descriptor.py` returning its `AgentDescriptor`, a `Dockerfile`, and the platform-specific config SETUP.md references (e.g. `agents/data_prep/adk_config.yaml`, `agents/causal_estimation/` AgentCore config, `agents/readout/` Azure OpenAI config).
- `orchestrator/hub.py` — runs the three-step workflow; for each step it asks the router which agent to use, then calls it. `orchestrator/a2a.py` — the A2A handoff; include a `SEQUENTIAL=true` fallback path (hub calls steps directly, no A2A) for reliability.
- Every agent registers the `report(reason)` self-diagnostic tool — implement it in `signals/self_report_tool.py`.
- **MOCK mode**: when `MOCK=true`, agents return canned-but-realistic step outputs (a data-prep agent returns a validation summary, a causal agent returns an effect estimate with a CI, a readout agent returns a memo) with plausible token counts and latency. When `MOCK=false`, they call the real platform.
- The `causal_estimation` agent's mock must be able to produce an effect estimate that is *deliberately out of plausible bounds* when a "degraded" flag is set — this is the demo's silent-failure case. Same for `readout` overstating certainty.
- The GCP agent (`data_prep`) gets a real implementation behind the mock first; AWS and Azure agents can stay mock-only until Milestone 7, but their *descriptors* must be real so the router sees them.

**Checkpoint**: `pytest tests/test_agents.py` — each agent, in MOCK mode, accepts an `AgentRequest` and returns a valid `AgentResponse`; the orchestrator runs all three steps end to end; the causal agent's degraded mode produces an out-of-bounds estimate. **Stop here.**

### Milestone 2 — Harness + Scorers + Seed Data
*Goal: can evaluate any agent and produce `EvalScore`s. This unblocks the router.*

- `harness/tasks/` — one YAML golden set per task family (`data_prep`, `causal_estimation`, `readout`), ~20 tasks each. Each task: `{id, prompt, expected, difficulty}`.
- `harness/scorers/tool_call.py` — AST-based tool-call correctness check.
- `harness/scorers/end_state.py` — compares final state to expected; for `causal_estimation`, checks the estimate falls within expected bounds.
- `harness/scorers/judge.py` — LLM-as-judge with the bias controls from README (randomized order, separate judge model, rubric decomposition). Mockable.
- `harness/inspect_runner.py` — wraps `inspect_ai`; runs an agent over a task family k times; computes `pass^k` + bootstrap CIs; emits `EvalScore`.
- `scripts/seed_demo_data.py` — **critical**: generates a realistic corpus of `AgentResponse`s, `Signal`s, and `EvalScore`s for all agents across all task families, with deliberate, documented quality differences — specifically, a "before upgrade" healthy regime and an "after upgrade" degraded regime for the causal and readout agents, so the loop has a real drift to detect. Write it so the demo's numbers are reproducible.

**Checkpoint**: `make seed` populates a local SQLite (mock BigQuery). `pytest tests/test_harness.py` — running the harness on a seeded agent yields `EvalScore`s with sane CIs; the degraded causal agent scores measurably lower. **Stop here.**

### Milestone 3 — Mesh Federation Layer
*Goal: one unified registry + signal view over (mock) multi-cloud sources.*

- `mesh/adapters/base.py` — adapter interface:
  ```python
  class CloudAdapter(ABC):
      @abstractmethod
      def list_agents(self) -> list[AgentDescriptor]: ...
      @abstractmethod
      def pull_signals(self, since: datetime) -> list[Signal]: ...
      @abstractmethod
      def pull_eval_scores(self, since: datetime) -> list[EvalScore]: ...
  ```
- Implement `gcp.py`, `aws.py`, `azure.py`. Each works in MOCK mode now (reads seeded data); real API calls behind the mock, flagged where the I/O '26 surfaces are uncertain.
- `mesh/registry.py` — merges all adapters into one canonical catalog; GCP Agent Registry is the source of truth; cross-cloud agents carry `mesh.platform` + `mesh.external_id`.
- `common/bq.py` — read/write helpers; SQLite-backed when `MOCK=true`, BigQuery when not.

**Checkpoint**: `pytest tests/test_mesh.py` — federation returns all workflow agents and their normalized signals from the four adapters. **Stop here.**

### Milestone 4 — The Router
*Goal: both routers working; the headline Pareto chart generable. THE core deliverable.*

- `router/features.py` — builds the `(request, agent)` feature vector per README (request embedding, capability one-hot, platform one-hot, eval-score history, recent signal rates, cost, latency). Embeddings via `gemini-embedding-001`; mockable with a deterministic fake embedder.
- `router/baseline_embed_match.py` — cosine match + cost/latency-weighted argmax. **Build and verify this fully before touching the learned router.**
- `router/learned_router.py` — LightGBM `P(success | request, agent)`; trains on seeded eval logs; decision rule `argmax P(success)/cost^λ`.
- `router/bandit.py` — LinUCB wrapper for cold-start agents (`<20` calls).
- `router/cascade.py` — cheap-first, escalate-on-low-confidence.
- `router/server.py` — FastAPI: `POST /route` returns `RouteDecision`; `GET /stream` Server-Sent Events feed of decisions for the console; `/slack/interactive` + `/slack/commands` endpoints (placeholders wired per SETUP.md § 1.7 / § 4.4).
- A script to produce the four-curve Pareto chart from seeded data.

**Checkpoint**: `pytest tests/test_router.py` — baseline and learned both return valid `RouteDecision`s; the learned router's Pareto curve dominates the baseline on seeded data (this is hypothesis H1 — if it fails on seeded data, the seed data or features are wrong). **Stop here.**

### Milestone 5 — Signal Layer + Sentry
*Goal: cheap online signals on every trace; drift detection.*

- `signals/regex/patterns.py` — failure-phrase keyword patterns → `Signal`s.
- `signals/explicit/collectors.py` — tool-error/latency/cost/handoff-failure → `Signal`s.
- `signals/classifiers/` — four DistilBERT binary classifiers (**refusal, task_failure, low_confidence_output, malformed_handoff** — matching README §1). `train.py` fine-tunes on a small labeled set (generate it in seed data); `infer.py` runs CPU inference; **co-host inside `router/server.py`'s container** — no separate endpoint (per the cheap-cloud decision).
- `sentry/offline_regression.py` — McNemar's test + bootstrap CI + Benjamini-Hochberg across task families.
- `sentry/online_cusum.py` — CUSUM/EWMA control charts on signal rates.

**Checkpoint**: `pytest tests/test_signals.py` — classifiers load and classify; CUSUM fires on an injected drift in seeded data; McNemar correctly flags a seeded regression and correctly does *not* flag noise. **Stop here.**

### Milestone 6 — Triage Agent + the Localization Loop
*Goal: the headline. The triage agent localizes a failure to the step that caused it — separating cause from symptom — and turns it into new eval tasks.*

- `triage/cluster.py` — embed seeded traces, UMAP-reduce, HDBSCAN cluster.
- `triage/localize.py` — **the crown jewel.** Given a failure cluster and the pipeline's step graph, attribute the regression to the step that *caused* it, distinguishing it from downstream steps that merely *propagated* a bad intermediate state. Uses step-local signals, the out-of-bounds oracle where available, and the trace ordering. Emits the cause step, the symptom step(s), and a confidence basis.
- `triage/generate_tasks.py` — Gemini 3.5 Flash prompt: cluster → one-line root cause + step localization (cause vs. symptom) + 3–5 `proposed_tasks`. Mockable. (Use 3.5 Flash, not a Pro model — the continuous-loop economics in README depend on Flash cost.)
- `triage/a2ui_surface.py` — posts an A2UI card to Slack with Approve/Reject; handles the interaction callback.
- `triage/runner.py` — Cloud Run job entrypoint; on approval, fans out new tasks into the harness golden set (and, when `MOCK=false`, into GCP Agent Evaluation + AWS AgentCore eval config).

**Checkpoint**: `pytest tests/test_triage.py` — a seeded failure cluster yields a root cause, **correct step localization (the cause step, not the downstream symptom step)**, and proposed tasks; approval appends them to the harness golden set. **Stop here.**

### Milestone 7 — Real Cloud Wiring
*Goal: flip `MOCK=false`; the deferred SETUP.md steps now unblock.*

- Build and push every agent container (this is what unblocks SETUP.md § 2.3 step 4 and § 2.4).
- Implement the real API paths in each adapter; verify the I/O '26 surfaces (Managed Agents, `bedrock-agentcore-control`) against current docs — this is the milestone where guesses get corrected.
- Wire OTel export → Cloud Trace → BigQuery for real.
- Run the SETUP.md deferred steps in order: § 2.3 step 4, § 2.4, § 2.6, then the Azure equivalents.

**Checkpoint**: `python scripts/smoke_test.py` against real clouds — a request routes to a real agent on each of the three clouds and returns a real response with a real trace. **Stop here.**

### Milestone 8 — The Console
*Goal: the visual demo. Five views, built to the visual spec.*

**Read `CONSOLE_DESIGN.md` before starting this milestone — it is the authoritative visual spec.** It defines the aesthetic direction (dark "instrument panel"), the design tokens, the cause-vs-symptom color language, and the per-view layout. Do not improvise the look; execute the spec.

- Scaffold `console/` — Next.js + Tailwind + shadcn/ui. Apply the design tokens from `CONSOLE_DESIGN.md` §2 (dark theme, the state color language, the specified font pairings — **not** the default Inter/Material look).
- `console/lib/api.ts` — typed client for the router service.
- Five views, per `CONSOLE_DESIGN.md` §4: **Pipeline** (the workflow as connected step-nodes with the three health states and the animated propagation edge — the headline view), **Triage** (streaming reasoning, the localization verdict card, the Approve button), **Pareto** (the restyled cost-vs-quality chart), **Signals** (per-step signal sparklines), **Router** (live decision feed).
- **Reset feature.** The Reset feature is specified in three places:
  1. **The feature itself**: A visible "Reset to the start of the demo" control that restores the BigQuery demo tables to their pre-failure seeded state in one action.
  2. **The design consequence (decide-before-you-build)**: The loop's write path (Approve, re-score, reroute) must write to **demo-scoped** tables, not a global production golden set. If the build agent writes Approve globally and it is discovered later, retrofitting scoping is painful. This is a stated constraint before the Approve handler exists.
  3. **The checkpoint**: Verifies Reset works by running the loop twice with a Reset between and confirming identical results.
- Priority order if time is short: Pipeline, Triage, Pareto to full polish; Signals and Router functional and on-theme. Reset is not optional — it is required for the shareable link and for rehearsal.
- Containerize; deploy per SETUP.md § 4.3 and `DEPLOY.md` (separate Cloud Run service, calls the router by URL — not one container with two processes).

**Checkpoint**: console runs locally against the router; all five views render real (seeded then live) data; the Pipeline view's cause/symptom states are visually unmistakable per the `CONSOLE_DESIGN.md` §6 checklist; the Reset control restores the pre-failure state, and running the loop twice with a Reset between yields the same result both times. **Stop here.**

### Milestone 9 — Demo Polish
- `docs/DEMO.md` — the demo script with per-beat timing and who-clicks-what (mirrors PITCH.md's demo script; target 3:00, ~3:15 ceiling).
- `docs/METHODOLOGY.md` — **must be completed and committed before any real-cloud data is collected** (the pre-registration). H1–H5 thresholds, statistical decision rules.
- `scripts/smoke_test.py` hardened; `--min-instances=1` set on router + console.
- Three full dry-runs.

**Checkpoint**: full demo runs end-to-end at ~3:00 (≤ 3:15 ceiling). Repo ready to make public.

---

## Build Order Summary

The milestones are dependency-ordered; build them in sequence:

- **Milestones 0–3** lay the foundation: contracts, the agents and orchestrator, the harness, the cross-cloud federation layer. Everything runs in MOCK mode — no cloud credentials needed.
- **Milestone 4** is the router (baseline first, then learned + bandit) — the piece that acts on what the loop learns.
- **Milestone 5** is the signal layer and drift sentry.
- **Milestone 6** is the triage agent and the localization loop — the headline. It localizes a failure to the step that caused it (cause vs. symptom) and turns that into new eval tasks. Build this on top of an already-working system.
- **Milestone 7** flips `MOCK=false` and wires the real clouds; the deferred SETUP.md steps unblock here.
- **Milestone 8** is the console; **Milestone 9** is demo polish and the methodology pre-registration.

If a coding agent is doing the build, keep it strictly in this order — Milestone 6 is meaningless without 0–5 underneath it, and the console (8) over a non-existent router (4) is wasted effort.

---

## What the Coding Agent Should NOT Do

- Do not skip the MOCK layer "to save time." The mock layer is what lets every milestone run without waiting on cloud credentials, and it is what makes the demo reproducible. It is not optional scaffolding — it is the development substrate.
- Do not change `common/schema.py` after Milestone 0 without human sign-off.
- Do not invent cloud API calls. If the Managed Agents or AgentCore API is uncertain, write the interface, write the mock, and leave a `# VERIFY:` comment for the human.
- Do not build the console before Milestone 4. A pretty UI over a non-existent router is wasted time.
- Do not deploy anything to a real cloud before Milestone 7. Everything runs locally in MOCK mode until then.
- Do not put real credentials, project IDs, or ARNs in any committed file.

---

## First Prompt to Give the Coding Agent

> Read `README.md`, `SCAFFOLD.md`, and `SETUP.md` in this repo. Then execute `SCAFFOLD.md` starting at Milestone 0. Build only Milestone 0, stop at its checkpoint, and show me `common/schema.py` and the directory tree for review. Do not proceed to Milestone 1 until I confirm. Follow the golden rules in SCAFFOLD.md — especially: keep everything runnable in MOCK mode, never guess cloud APIs, and never commit credentials.

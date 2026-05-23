from datetime import datetime
from enum import Enum

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
    kind: str  # "refusal"|"task_failure"|"low_confidence_output"|
               # "malformed_handoff"|"out_of_bounds"|"tool_error"|
               # "latency"|"cost"|"self_report"
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
    localization_basis: str  # how the cause was attributed (oracle |
                             # signal drift | trace order)
    root_cause: str               # one-line, LLM-generated
    proposed_tasks: list[dict]    # [{prompt, task_family, expected}]
    status: str                   # "proposed"|"approved"|"rejected"

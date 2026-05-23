import uuid

from agents.causal_estimation.agent import CausalEstimationAgent
from agents.data_prep.agent import DataPrepAgent
from agents.readout.agent import ReadoutAgent
from agents.spares.causal_spare import CausalEstimationSpareAgent
from agents.spares.data_prep_spare import DataPrepSpareAgent
from agents.spares.readout_spare import ReadoutSpareAgent
from common.schema import AgentRequest, TaskFamily
from orchestrator.a2a import handoff_data

# Map TaskFamily to standard healthy agents
DEFAULT_AGENTS = {
    TaskFamily.DATA_PREP: DataPrepAgent(),
    TaskFamily.CAUSAL_ESTIMATION: CausalEstimationAgent(),
    TaskFamily.READOUT: ReadoutAgent()
}

# Map TaskFamily to spare agents
SPARE_AGENTS = {
    TaskFamily.DATA_PREP: DataPrepSpareAgent(),
    TaskFamily.CAUSAL_ESTIMATION: CausalEstimationSpareAgent(),
    TaskFamily.READOUT: ReadoutSpareAgent()
}

class OrchestratorHub:
    def __init__(self, routing_overrides: dict = None):
        """
        OrchestratorHub drives the three-step experiment readout workflow.
        Allows overriding which agent is used for each step (e.g. for spare routing).
        routing_overrides: dict of {TaskFamily: agent_instance}
        """
        self.routing_overrides = routing_overrides or {}

    def get_agent(self, step: TaskFamily, use_spare: bool = False):
        if step in self.routing_overrides:
            return self.routing_overrides[step]
        return SPARE_AGENTS[step] if use_spare else DEFAULT_AGENTS[step]

    def run_workflow(self, initial_prompt: str, degrade_step: TaskFamily = None) -> dict:
        request_id = str(uuid.uuid4())

        # Step 1: Data Prep
        step1_agent = self.get_agent(TaskFamily.DATA_PREP)
        s1_prompt = initial_prompt
        if degrade_step == TaskFamily.DATA_PREP:
            s1_prompt += " [degraded]"
        s1_req = AgentRequest(
            request_id=request_id,
            prompt=s1_prompt,
            task_family=TaskFamily.DATA_PREP
        )
        s1_res = step1_agent.handle(s1_req)

        # Handoff to Step 2: Causal Estimation
        s2_input = handoff_data("data_prep", "causal_estimation", s1_res)
        s2_prompt = f"{s2_input}\nPerform causal estimation on this data."
        if degrade_step == TaskFamily.CAUSAL_ESTIMATION:
            s2_prompt += " [degraded]"
        step2_agent = self.get_agent(TaskFamily.CAUSAL_ESTIMATION)
        s2_req = AgentRequest(
            request_id=request_id,
            prompt=s2_prompt,
            task_family=TaskFamily.CAUSAL_ESTIMATION
        )
        s2_res = step2_agent.handle(s2_req)

        # Handoff to Step 3: Readout
        s3_input = handoff_data("causal_estimation", "readout", s2_res)
        s3_prompt = f"{s3_input}\nDraft the final readout memo based on the causal results."
        if degrade_step == TaskFamily.READOUT:
            s3_prompt += " [degraded]"
        step3_agent = self.get_agent(TaskFamily.READOUT)
        s3_req = AgentRequest(
            request_id=request_id,
            prompt=s3_prompt,
            task_family=TaskFamily.READOUT
        )
        s3_res = step3_agent.handle(s3_req)

        total_latency = s1_res.latency_ms + s2_res.latency_ms + s3_res.latency_ms
        total_tokens_in = s1_res.tokens_in + s2_res.tokens_in + s3_res.tokens_in
        total_tokens_out = s1_res.tokens_out + s2_res.tokens_out + s3_res.tokens_out

        return {
            "request_id": request_id,
            "steps": {
                "data_prep": s1_res,
                "causal_estimation": s2_res,
                "readout": s3_res
            },
            "metrics": {
                "total_latency_ms": total_latency,
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out
            }
        }

if __name__ == "__main__":
    hub = OrchestratorHub()
    print("=== Running healthy workflow ===")
    res = hub.run_workflow("Randomization validation of Experiment #1093")
    print(f"Workflow ID: {res['request_id']}")
    print(f"Step 3 Output:\n{res['steps']['readout'].output}")
    print(f"Total Latency: {res['metrics']['total_latency_ms']:.2f} ms")

    print("\n=== Running degraded causal estimation workflow ===")
    res_deg = hub.run_workflow(
        "Randomization validation of Experiment #1093",
        degrade_step=TaskFamily.CAUSAL_ESTIMATION
    )
    print(f"Step 2 Output:\n{res_deg['steps']['causal_estimation'].output}")
    print(
        f"Step 2 Self-reports: "
        f"{res_deg['steps']['causal_estimation'].self_reports}"
    )

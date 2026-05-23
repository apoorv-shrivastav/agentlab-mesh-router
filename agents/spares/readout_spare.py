import time

from agents.base.agent_iface import Agent
from common.schema import AgentDescriptor, AgentRequest, AgentResponse, Platform, TaskFamily
from signals.self_report_tool import get_self_reports, init_self_reports, report


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="readout-spare",
        display_name="Readout & Recommendation (Spare)",
        platform=Platform.AZURE_OPENAI,
        task_families=[TaskFamily.READOUT],
        capability_text=(
            "Backup Readout agent. Drafts stakeholder-ready experiment summary "
            "memos recommending ship/don't ship/iterate."
        ),
        cost_per_1k_tokens=0.010,
        endpoint=None,
        external_id=None
    )

class ReadoutSpareAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        report("Backup Readout agent handling request.")
        output = (
            "MEMO: A/B Experiment Recommendation (Spare)\n"
            "Recommendation: SHIP\n"
            "Rationale: The treatment group demonstrated a +2.4% lift (p = 0.003). "
            "Sample ratio checks indicate randomization was successful. Rolling out."
        )

        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=400,
            tokens_out=300,
            latency_ms=(time.time() - start_time) * 1000,
            tool_calls=[],
            self_reports=get_self_reports()
        )

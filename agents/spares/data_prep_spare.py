import time

from agents.base.agent_iface import Agent
from common.schema import AgentDescriptor, AgentRequest, AgentResponse, Platform, TaskFamily
from signals.self_report_tool import get_self_reports, init_self_reports, report


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="data-prep-spare",
        display_name="Data Prep (Spare)",
        platform=Platform.GCP_ADK,
        task_families=[TaskFamily.DATA_PREP],
        capability_text=(
            "Backup Data Prep agent. Pulls A/B experiment event data, "
            "performs sample ratio mismatch (SRM) checks, and validates randomization."
        ),
        cost_per_1k_tokens=0.000075,
        endpoint=None,
        external_id=None
    )

class DataPrepSpareAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        # Spares remain healthy and do not trigger degradation logic
        report("Backup Data Prep agent handling request.")
        output = (
            "SRM validation PASSED (Spare).\n"
            "Total users: 10,000 (Treatment: 5,020, Control: 4,980)\n"
            "SRM p-value: 0.69 (randomization intact)"
        )

        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=150,
            tokens_out=250,
            latency_ms=(time.time() - start_time) * 1000,
            tool_calls=[],
            self_reports=get_self_reports()
        )

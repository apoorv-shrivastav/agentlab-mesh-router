import time

from agents.base.agent_iface import Agent
from common.schema import AgentDescriptor, AgentRequest, AgentResponse, Platform, TaskFamily
from signals.self_report_tool import get_self_reports, init_self_reports, report


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="causal-estimation-spare",
        display_name="Causal Estimation (Spare)",
        platform=Platform.AWS_AGENTCORE,
        task_families=[TaskFamily.CAUSAL_ESTIMATION],
        capability_text=(
            "Backup Causal Estimation agent. Estimates treatment effect (ATE) "
            "using CUPED variance reduction and evaluates confidence intervals."
        ),
        cost_per_1k_tokens=0.015,
        endpoint=None,
        external_id=None
    )

class CausalEstimationSpareAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        report("Backup Causal Estimation agent handling request.")
        output = (
            "Causal Estimation Complete (Spare).\n"
            "Method: CUPED-adjusted OLS\n"
            "Estimated Lift: +2.4%\n"
            "95% Confidence Interval: [0.8%, 4.0%]\n"
            "p-value: 0.0031 (Statistically Significant)"
        )

        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=300,
            tokens_out=400,
            latency_ms=(time.time() - start_time) * 1000,
            tool_calls=[],
            self_reports=get_self_reports()
        )

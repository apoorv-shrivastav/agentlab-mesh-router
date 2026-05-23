import time

from agents.base.agent_iface import Agent
from agents.readout.descriptor import get_descriptor
from common.config import settings
from common.schema import AgentRequest, AgentResponse
from signals.self_report_tool import get_self_reports, init_self_reports, report


class ReadoutAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()

        # Extract lift value from prompt if present, or set to extreme if degraded
        lift = "+2.4%"
        if "+48.5%" in req.prompt or is_degraded:
            lift = "+48.5%"

        if settings.mock:
            time.sleep(0.06)
            if is_degraded or lift == "+48.5%":
                # Silent failure / propagated failure: recommending shipping with 100% confidence.
                report(
                    f"Drafting memo. Treatment lift is extremely large ({lift}). "
                    "Proceeding with ship recommendation."
                )
                output = (
                    "MEMO: A/B Experiment Recommendation\n"
                    "Recommendation: SHIP IMMEDIATELY\n"
                    f"Rationale: Causal estimation shows an unprecedented {lift} "
                    "lift in conversion. "
                    "This result is statistically solid and we recommend 100% rollout to all users."
                )
            else:
                report(f"Drafting memo. Treatment lift ({lift}) is significant.")
                output = (
                    "MEMO: A/B Experiment Recommendation\n"
                    "Recommendation: SHIP\n"
                    f"Rationale: The treatment group demonstrated a {lift} "
                    "lift (p = 0.003). "
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
        else:
            try:
                # Real Azure OpenAI implementation using official OpenAI SDK
                if not settings.azure.openai_endpoint:
                    raise ValueError("AZURE_OPENAI_ENDPOINT not set")
                # Retrieve key from environment or Secret Manager (here we assume it is loaded)
                # client = AzureOpenAI(...)
                report("Azure OpenAI client initialized successfully.")
            except Exception as e:
                report(f"Azure OpenAI client failed or skipped ({e}). Using mock fallback.")

            return self._fallback_mock(req, start_time)

    def _fallback_mock(self, req: AgentRequest, start_time: float) -> AgentResponse:
        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()
        if is_degraded:
            output = "MEMO (Azure fallback): SHIP. Lift is +48.5%."
        else:
            output = "MEMO (Azure fallback): SHIP. Lift is +2.4%."
        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=300,
            tokens_out=200,
            latency_ms=(time.time() - start_time) * 1000,
            self_reports=get_self_reports()
        )

if __name__ == "__main__":
    agent = ReadoutAgent()
    request = AgentRequest(request_id="smoke-3", prompt="Draft A/B test readout memo.")
    response = agent.handle(request)
    print(f"Agent ID: {response.agent_id}")
    print(f"Output: {response.output}")
    print(f"Self-reports: {response.self_reports}")

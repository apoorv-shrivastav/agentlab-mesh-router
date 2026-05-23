import time

from agents.base.agent_iface import Agent
from agents.causal_estimation.descriptor import get_descriptor
from common.config import settings
from common.schema import AgentRequest, AgentResponse
from signals.self_report_tool import get_self_reports, init_self_reports, report


class CausalEstimationAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()

        if settings.mock:
            time.sleep(0.08)
            if is_degraded:
                # Silent failure: Outputs a highly implausible positive lift (e.g. 48.5%)
                # without raising a hard crash, but records a warning in self-reports.
                report(
                    "CUPED covariate adjustment yielded unusually high variance. "
                    "Point estimate is extreme."
                )
                output = (
                    "Causal Estimation Complete.\n"
                    "Method: CUPED-adjusted OLS\n"
                    "Estimated Lift: +48.5%\n"
                    "95% Confidence Interval: [42.1%, 54.9%]\n"
                    "p-value: < 0.0001 (Highly Significant)"
                )
            else:
                report("ATE calculation completed with CUPED variance reduction.")
                output = (
                    "Causal Estimation Complete.\n"
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
        else:
            try:
                import boto3
                if not settings.aws.agentcore_runtime_arn:
                    raise ValueError("AGENTCORE_RUNTIME_ARN not set")
                    
                # AWS Bedrock AgentCore client call
                client = boto3.client('bedrock-agentcore-runtime', region_name=settings.aws.region)
                response = client.invoke_agent(
                    agentRuntimeArn=settings.aws.agentcore_runtime_arn,
                    inputText=req.prompt,
                    sessionId=req.request_id
                )
                output = response.get("outputText", "Causal estimation complete.")
                tokens_in = response.get("metrics", {}).get("inputTokens", 300)
                tokens_out = response.get("metrics", {}).get("outputTokens", 400)
                
                report("AWS Bedrock execution completed successfully.")
                
                return AgentResponse(
                    request_id=req.request_id,
                    agent_id=self.descriptor.agent_id,
                    output=output,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=(time.time() - start_time) * 1000,
                    self_reports=get_self_reports()
                )
            except Exception as e:
                report(f"AWS Bedrock execution failed ({e}). Using mock fallback.")
                return self._fallback_mock(req, start_time)


    def _fallback_mock(self, req: AgentRequest, start_time: float) -> AgentResponse:
        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()
        if is_degraded:
            output = "Causal Estimation Complete (AWS fallback). Estimated Lift: +48.5% (extreme)"
        else:
            output = "Causal Estimation Complete (AWS fallback). Estimated Lift: +2.4%"
        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=200,
            tokens_out=250,
            latency_ms=(time.time() - start_time) * 1000,
            self_reports=get_self_reports()
        )

if __name__ == "__main__":
    agent = CausalEstimationAgent()
    request = AgentRequest(request_id="smoke-2", prompt="Estimate treatment effects.")
    response = agent.handle(request)
    print(f"Agent ID: {response.agent_id}")
    print(f"Output: {response.output}")
    print(f"Self-reports: {response.self_reports}")

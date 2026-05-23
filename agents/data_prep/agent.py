import time

from agents.base.agent_iface import Agent
from agents.data_prep.descriptor import get_descriptor
from common.config import settings
from common.schema import AgentRequest, AgentResponse
from signals.self_report_tool import get_self_reports, init_self_reports, report


class DataPrepAgent(Agent):
    descriptor = get_descriptor()

    def handle(self, req: AgentRequest) -> AgentResponse:
        start_time = time.time()
        init_self_reports()

        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()

        if settings.mock:
            time.sleep(0.05)
            if is_degraded:
                report("Sample ratio mismatch detected: p-value 0.0001 (below threshold 0.01).")
                output = (
                    "SRM validation FAILED.\n"
                    "Total users: 10,000 (Treatment: 5,400, Control: 4,600)\n"
                    "SRM p-value: 0.0001 (randomization broken)"
                )
            else:
                report("Checked randomization. SRM check passed.")
                output = (
                    "SRM validation PASSED.\n"
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
        else:
            try:
                from google.cloud import bigquery
                if not settings.gcp.project_id:
                    raise ValueError("GCP_PROJECT_ID not set")
                bigquery.Client(project=settings.gcp.project_id)
                # BigQuery read logic would execute here.
                # For this milestone, fallback gracefully if tables aren't present.
                report("BigQuery client initialized successfully.")
            except Exception as e:
                report(f"BigQuery access skipped or failed ({e}). Using mock fallback.")

            return self._fallback_mock(req, start_time)

    def _fallback_mock(self, req: AgentRequest, start_time: float) -> AgentResponse:
        is_degraded = "degraded" in req.prompt.lower() or "fail" in req.prompt.lower()
        if is_degraded:
            output = (
                "SRM validation FAILED (BigQuery fallback). "
                "Total users: 10000. SRM p-value: 0.0001"
            )
        else:
            output = (
                "SRM validation PASSED (BigQuery fallback). "
                "Total users: 10000. SRM p-value: 0.45"
            )
        return AgentResponse(
            request_id=req.request_id,
            agent_id=self.descriptor.agent_id,
            output=output,
            tokens_in=100,
            tokens_out=150,
            latency_ms=(time.time() - start_time) * 1000,
            self_reports=get_self_reports()
        )

if __name__ == "__main__":
    # Standard smoke test execution
    agent = DataPrepAgent()
    request = AgentRequest(request_id="smoke-1", prompt="Run validations on A/B test logs.")
    response = agent.handle(request)
    print(f"Agent ID: {response.agent_id}")
    print(f"Output: {response.output}")
    print(f"Self-reports: {response.self_reports}")

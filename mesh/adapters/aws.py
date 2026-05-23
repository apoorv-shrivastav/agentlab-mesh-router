from datetime import datetime

from agents.causal_estimation.descriptor import get_descriptor as get_ce_desc
from agents.spares.causal_spare import get_descriptor as get_spare_desc
from common.bq import query_eval_scores, query_signals
from common.schema import AgentDescriptor, EvalScore, Signal
from mesh.adapters.base import CloudAdapter


class AWSAdapter(CloudAdapter):
    """AWS Cloud Adapter managing step 2 agents and spares telemetry."""

    def list_agents(self) -> list[AgentDescriptor]:
        return [get_ce_desc(), get_spare_desc()]

    def pull_signals(self, since: datetime) -> list[Signal]:
        # In real mode, this would query CloudWatch Logs for the agent traces.
        # In mock mode, we pull from the centralized database signals.
        aws_agent_ids = {a.agent_id for a in self.list_agents()}
        all_sigs = query_signals(since)
        return [s for s in all_sigs if s.agent_id in aws_agent_ids]

    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        # In real mode, this would query Bedrock AgentCore Online Evaluation Config.
        aws_agent_ids = {a.agent_id for a in self.list_agents()}
        all_scores = query_eval_scores(since)
        return [s for s in all_scores if s.agent_id in aws_agent_ids]

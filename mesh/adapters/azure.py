from datetime import datetime

from agents.readout.descriptor import get_descriptor as get_ro_desc
from agents.spares.readout_spare import get_descriptor as get_spare_desc
from common.bq import query_eval_scores, query_signals
from common.schema import AgentDescriptor, EvalScore, Signal
from mesh.adapters.base import CloudAdapter


class AzureAdapter(CloudAdapter):
    """Azure Cloud Adapter managing step 3 agents and spares telemetry."""

    def list_agents(self) -> list[AgentDescriptor]:
        return [get_ro_desc(), get_spare_desc()]

    def pull_signals(self, since: datetime) -> list[Signal]:
        # In real mode, this would query Azure Application Insights logs.
        # In mock mode, we pull from the centralized database signals.
        azure_agent_ids = {a.agent_id for a in self.list_agents()}
        all_sigs = query_signals(since)
        return [s for s in all_sigs if s.agent_id in azure_agent_ids]

    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        # In real mode, this would pull evaluation metrics.
        azure_agent_ids = {a.agent_id for a in self.list_agents()}
        all_scores = query_eval_scores(since)
        return [s for s in all_scores if s.agent_id in azure_agent_ids]

from datetime import datetime

from agents.data_prep.descriptor import get_descriptor as get_dp_desc
from agents.spares.data_prep_spare import get_descriptor as get_spare_desc
from common.bq import query_eval_scores, query_signals
from common.schema import AgentDescriptor, EvalScore, Signal
from mesh.adapters.base import CloudAdapter


class GCPAdapter(CloudAdapter):
    """GCP Cloud Adapter managing step 1 agents and spares telemetry."""

    def list_agents(self) -> list[AgentDescriptor]:
        return [get_dp_desc(), get_spare_desc()]

    def pull_signals(self, since: datetime) -> list[Signal]:
        # Filter signals to only include those originating from GCP agents
        gcp_agent_ids = {a.agent_id for a in self.list_agents()}
        all_sigs = query_signals(since)
        return [s for s in all_sigs if s.agent_id in gcp_agent_ids]

    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        # Filter eval scores to only include those originating from GCP agents
        gcp_agent_ids = {a.agent_id for a in self.list_agents()}
        all_scores = query_eval_scores(since)
        return [s for s in all_scores if s.agent_id in gcp_agent_ids]

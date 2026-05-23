from datetime import datetime

from common.schema import AgentDescriptor, EvalScore, Signal
from mesh.adapters.aws import AWSAdapter
from mesh.adapters.azure import AzureAdapter
from mesh.adapters.gcp import GCPAdapter

# Instantiated Cloud Adapters
ADAPTERS = [
    GCPAdapter(),
    AWSAdapter(),
    AzureAdapter()
]

def list_all_agents() -> list[AgentDescriptor]:
    """Retrieves all registered agents across GCP, AWS, and Azure."""
    agents = []
    for adapter in ADAPTERS:
        agents.extend(adapter.list_agents())
    return agents

def get_agent_by_id(agent_id: str) -> AgentDescriptor | None:
    """Retrieves a specific agent descriptor by its ID."""
    for agent in list_all_agents():
        if agent.agent_id == agent_id:
            return agent
    return None

def pull_all_signals(since: datetime) -> list[Signal]:
    """Federates and returns signals across all cloud adapters."""
    signals = []
    for adapter in ADAPTERS:
        signals.extend(adapter.pull_signals(since))
    # Sort by timestamp ascending
    signals.sort(key=lambda x: x.timestamp)
    return signals

def pull_all_eval_scores(since: datetime) -> list[EvalScore]:
    """Federates and returns evaluation scores across all cloud adapters."""
    scores = []
    for adapter in ADAPTERS:
        scores.extend(adapter.pull_eval_scores(since))
    scores.sort(key=lambda x: x.timestamp)
    return scores

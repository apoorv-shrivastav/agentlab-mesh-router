from datetime import datetime, timedelta

from common.schema import Platform
from mesh.adapters.aws import AWSAdapter
from mesh.adapters.azure import AzureAdapter
from mesh.adapters.gcp import GCPAdapter
from mesh.registry import get_agent_by_id, list_all_agents, pull_all_eval_scores, pull_all_signals
from mesh.schema import AgentDescriptor, EvalScore, Signal


def test_mesh_schema_reexports():
    assert AgentDescriptor is not None
    assert Signal is not None
    assert EvalScore is not None

def test_gcp_adapter():
    adapter = GCPAdapter()
    agents = adapter.list_agents()
    assert len(agents) == 2
    assert any(a.agent_id == "data-prep" for a in agents)
    assert any(a.agent_id == "data-prep-spare" for a in agents)

    # Verify that signals and scores can be retrieved (seeded in DB)
    since = datetime.utcnow() - timedelta(days=20)
    signals = adapter.pull_signals(since)
    scores = adapter.pull_eval_scores(since)

    assert isinstance(signals, list)
    assert isinstance(scores, list)

def test_aws_adapter():
    adapter = AWSAdapter()
    agents = adapter.list_agents()
    assert len(agents) == 2
    assert any(a.agent_id == "causal-estimation" for a in agents)

    since = datetime.utcnow() - timedelta(days=20)
    signals = adapter.pull_signals(since)
    assert len(signals) > 0
    assert all(s.agent_id in ("causal-estimation", "causal-estimation-spare") for s in signals)

def test_azure_adapter():
    adapter = AzureAdapter()
    agents = adapter.list_agents()
    assert len(agents) == 2
    assert any(a.agent_id == "readout" for a in agents)

    since = datetime.utcnow() - timedelta(days=20)
    signals = adapter.pull_signals(since)
    assert len(signals) > 0
    assert all(s.agent_id in ("readout", "readout-spare") for s in signals)

def test_mesh_registry():
    agents = list_all_agents()
    assert len(agents) == 6  # 3 primary + 3 spares

    desc = get_agent_by_id("causal-estimation")
    assert desc is not None
    assert desc.platform == Platform.AWS_AGENTCORE

    since = datetime.utcnow() - timedelta(days=20)
    all_signals = pull_all_signals(since)
    all_scores = pull_all_eval_scores(since)

    assert len(all_signals) > 0
    assert len(all_scores) > 0
    # Signals sorted ascending
    assert all_signals[0].timestamp <= all_signals[-1].timestamp

from agents.causal_estimation.agent import CausalEstimationAgent
from agents.data_prep.agent import DataPrepAgent
from agents.readout.agent import ReadoutAgent
from agents.spares.causal_spare import CausalEstimationSpareAgent
from agents.spares.data_prep_spare import DataPrepSpareAgent
from agents.spares.readout_spare import ReadoutSpareAgent
from common.schema import AgentRequest, TaskFamily
from orchestrator.hub import OrchestratorHub


def test_data_prep_agent_healthy():
    agent = DataPrepAgent()
    req = AgentRequest(request_id="test-1", prompt="Validate randomization data.")
    res = agent.handle(req)
    assert res.agent_id == "data-prep"
    assert "PASSED" in res.output
    assert len(res.self_reports) == 1
    assert "SRM check passed" in res.self_reports[0]

def test_data_prep_agent_degraded():
    agent = DataPrepAgent()
    req = AgentRequest(request_id="test-2", prompt="Validate randomization [degraded]")
    res = agent.handle(req)
    assert res.agent_id == "data-prep"
    assert "FAILED" in res.output
    assert any("mismatch" in r.lower() for r in res.self_reports)

def test_causal_agent_healthy():
    agent = CausalEstimationAgent()
    req = AgentRequest(request_id="test-3", prompt="Calculate ATE.")
    res = agent.handle(req)
    assert res.agent_id == "causal-estimation"
    assert "+2.4%" in res.output
    assert any("completed" in r.lower() for r in res.self_reports)

def test_causal_agent_degraded():
    agent = CausalEstimationAgent()
    req = AgentRequest(request_id="test-4", prompt="Calculate ATE [degraded]")
    res = agent.handle(req)
    assert res.agent_id == "causal-estimation"
    assert "+48.5%" in res.output
    assert any("extreme" in r.lower() or "high variance" in r.lower() for r in res.self_reports)

def test_readout_agent_healthy():
    agent = ReadoutAgent()
    req = AgentRequest(request_id="test-5", prompt="Draft memo.")
    res = agent.handle(req)
    assert res.agent_id == "readout"
    assert "+2.4%" in res.output
    assert any("significant" in r.lower() for r in res.self_reports)

def test_readout_agent_degraded():
    agent = ReadoutAgent()
    req = AgentRequest(request_id="test-6", prompt="Draft memo [degraded]")
    res = agent.handle(req)
    assert res.agent_id == "readout"
    assert "+48.5%" in res.output
    assert any("extreme" in r.lower() for r in res.self_reports)

def test_spares_healthy():
    dp_spare = DataPrepSpareAgent()
    c_spare = CausalEstimationSpareAgent()
    r_spare = ReadoutSpareAgent()

    dp_res = dp_spare.handle(AgentRequest(request_id="s1", prompt="[degraded]"))
    c_res = c_spare.handle(AgentRequest(request_id="s2", prompt="[degraded]"))
    r_res = r_spare.handle(AgentRequest(request_id="s3", prompt="[degraded]"))

    # Spares should remain healthy even if prompt triggers are passed
    assert "PASSED" in dp_res.output
    assert "+2.4%" in c_res.output
    assert "SHIP" in r_res.output

def test_hub_orchestrated_workflow_healthy():
    hub = OrchestratorHub()
    res = hub.run_workflow("Randomization validation of Experiment #1093")
    assert "steps" in res
    assert "metrics" in res
    assert res["steps"]["data_prep"].success is None
    assert "SRM validation PASSED" in res["steps"]["data_prep"].output
    assert "+2.4%" in res["steps"]["causal_estimation"].output
    assert "Recommendation: SHIP" in res["steps"]["readout"].output
    assert res["metrics"]["total_latency_ms"] > 0
    assert res["metrics"]["total_tokens_in"] > 0
    assert res["metrics"]["total_tokens_out"] > 0

def test_hub_orchestrated_workflow_degraded():
    hub = OrchestratorHub()
    res = hub.run_workflow("Run A/B test analysis.", degrade_step=TaskFamily.CAUSAL_ESTIMATION)
    # Causal step should be degraded, readout should recommend ship with 48.5%
    assert "+48.5%" in res["steps"]["causal_estimation"].output
    assert "unprecedented +48.5% lift" in res["steps"]["readout"].output

from datetime import datetime, timedelta

from agents.causal_estimation.agent import CausalEstimationAgent
from common.bq import query_signals, write_agent_response, write_signal
from common.schema import AgentResponse, Signal, TaskFamily
from harness.inspect_runner import run_evaluation
from harness.scorers.end_state import score_end_state
from harness.scorers.judge import run_llm_judge
from harness.scorers.tool_call import score_response_tool_calls, verify_tool_call_syntax


def test_db_storage():
    resp = AgentResponse(
        request_id="test-resp-1",
        agent_id="test-agent",
        output="Causal lift is +2.4%",
        success=None,
        tokens_in=100,
        tokens_out=150,
        latency_ms=250.0,
        tool_calls=[],
        self_reports=[]
    )
    # Verify write executes without raising exception
    write_agent_response(resp, success=True)

    sig = Signal(
        request_id="test-resp-1",
        agent_id="test-agent",
        timestamp=datetime.utcnow(),
        kind="latency",
        value=250.0,
        source="explicit"
    )
    write_signal(sig)

    signals = query_signals(datetime.utcnow() - timedelta(minutes=5))
    assert len(signals) > 0
    assert signals[-1].request_id == "test-resp-1"

def test_tool_call_scorer():
    resp = AgentResponse(
        request_id="test-resp-1",
        agent_id="test-agent",
        output="Result",
        success=None,
        tokens_in=10,
        tokens_out=10,
        latency_ms=5.0,
        tool_calls=[{"name": "report", "args": {"reason": "Testing"}}],
        self_reports=["Warning"]
    )
    assert score_response_tool_calls(resp, "report") is True
    assert score_response_tool_calls(resp, "other_tool") is False

    code = "report('Failed to open database.')"
    assert verify_tool_call_syntax(code, "report") is True
    assert verify_tool_call_syntax(code, "query") is False

def test_end_state_scorer():
    resp1 = AgentResponse(
        request_id="r1", agent_id="a1", output="Estimated Lift: +2.45%",
        tokens_in=10, tokens_out=10, latency_ms=1.0
    )
    # Float conversion matches within +/- 1.0 tolerance
    assert score_end_state(resp1, "+2.4%") is True
    assert score_end_state(resp1, "+4.5%") is False

    resp2 = AgentResponse(
        request_id="r2", agent_id="a1", output="SRM validation PASSED",
        tokens_in=10, tokens_out=10, latency_ms=1.0
    )
    assert score_end_state(resp2, "SRM validation PASSED") is True

def test_llm_judge():
    resp = AgentResponse(
        request_id="r1",
        agent_id="a1",
        output="Memo: ship the feature because conversion lift is positive.",
        tokens_in=10,
        tokens_out=10,
        latency_ms=1.0
    )
    # Under MOCK=true, defaults to keyword matching
    assert run_llm_judge(resp, "Check recommendation", "ship") is True
    assert run_llm_judge(resp, "Check recommendation", "reject") is False

def test_inspect_runner():
    agent = CausalEstimationAgent()
    # Runs evaluation on the causal_estimation task family
    score = run_evaluation(agent, TaskFamily.CAUSAL_ESTIMATION, n_trials=1)
    assert score.agent_id == "causal-estimation"
    assert score.task_family == TaskFamily.CAUSAL_ESTIMATION
    assert score.n_trials == 20
    assert 0.0 <= score.pass_k <= 1.0
    assert score.ci_low <= score.ci_high

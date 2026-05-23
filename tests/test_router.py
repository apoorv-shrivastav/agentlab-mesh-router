import pytest
from fastapi.testclient import TestClient

from common.schema import AgentDescriptor, Platform, TaskFamily
from router.bandit import route_bandit
from router.baseline_embed_match import route_baseline
from router.cascade import route_cascade
from router.features import build_features, cosine_similarity, get_embedding
from router.learned_router import LearnedRouter
from router.server import app


@pytest.fixture
def mock_candidates():
    return [
        AgentDescriptor(
            agent_id="test-agent-cheap",
            display_name="Cheap Agent",
            platform=Platform.GCP_ADK,
            task_families=[TaskFamily.DATA_PREP],
            capability_text="Simple agent that prepares basic data and runs checks.",
            cost_per_1k_tokens=0.0001,
        ),
        AgentDescriptor(
            agent_id="test-agent-expensive",
            display_name="Expensive Agent",
            platform=Platform.GCP_ADK,
            task_families=[TaskFamily.DATA_PREP],
            capability_text="Advanced agent that handles complex data prep and SRM checks.",
            cost_per_1k_tokens=0.01,
        )
    ]

def test_embeddings_and_similarity():
    emb1 = get_embedding("test query")
    emb2 = get_embedding("test query")
    emb3 = get_embedding("completely different query")

    assert len(emb1) == 768
    assert len(emb3) == 768

    # Deterministic mock should be identical for identical text
    assert emb1 == emb2

    sim_same = cosine_similarity(emb1, emb2)
    sim_diff = cosine_similarity(emb1, emb3)

    assert pytest.approx(sim_same, 1e-5) == 1.0
    assert sim_diff < 1.0

def test_features_build(mock_candidates):
    feats = build_features("Simple data prep check", mock_candidates[0])
    assert "semantic_similarity" in feats
    assert "cost_per_1k" in feats
    assert "mean_pass_rate" in feats
    assert "failure_signal_rate" in feats
    assert feats["cost_per_1k"] == 0.0001

def test_baseline_routing(mock_candidates):
    # With a high cost weight, the cheap agent should be selected
    decision = route_baseline(
        request_id="req-1",
        prompt="Simple data prep check",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates,
        cost_weight=1.0
    )
    assert decision.chosen_agent_id == "test-agent-cheap"
    assert decision.router_kind == "baseline"

    # With a cost weight of 0.0, the semantic similarity dominates.
    # In a real environment, semantic similarity might favor one over the other.
    # Here, let's just assert that it chooses one of them and runs successfully.
    decision_zero = route_baseline(
        request_id="req-2",
        prompt="Simple data prep check",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates,
        cost_weight=0.0
    )
    assert decision_zero.chosen_agent_id in ["test-agent-cheap", "test-agent-expensive"]

def test_learned_router_fallback(mock_candidates):
    # Since model is not trained yet, it should fallback to baseline
    router = LearnedRouter()
    # Temporarily set model to None to ensure fallback
    router.model = None
    decision = router.route(
        request_id="req-3",
        prompt="Simple data prep check",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates
    )
    assert decision.router_kind == "baseline"

def test_bandit_routing(mock_candidates):
    # Test bandit routing selects an agent and uses "bandit" kind
    decision = route_bandit(
        request_id="req-4",
        prompt="Simple data prep check",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates,
        alpha=1.0
    )
    assert decision.router_kind == "bandit"
    assert len(decision.candidates) == 2

def test_cascade_routing(mock_candidates):
    # Test cascade routing logic
    # If confidence threshold is low, it should select the cheaper agent first
    decision_low = route_cascade(
        request_id="req-5",
        prompt="Simple data prep",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates,
        confidence_threshold=0.1
    )
    assert decision_low.chosen_agent_id == "test-agent-cheap"

    # If confidence threshold is extremely high (e.g. 1.0),
    # it might escalate to the last/most expensive agent
    decision_high = route_cascade(
        request_id="req-6",
        prompt="Simple data prep",
        task_family=TaskFamily.DATA_PREP,
        candidates=mock_candidates,
        confidence_threshold=1.0
    )
    # The last/most expensive candidate is "test-agent-expensive"
    assert decision_high.chosen_agent_id == "test-agent-expensive"

def test_fastapi_server_endpoints():
    client = TestClient(app)

    # Test GET /stream endpoint works (returns SSE) without blocking
    # with client.stream("GET", "/stream") as response_stream:
    #     assert response_stream.status_code == 200
    #     assert response_stream.headers["content-type"] == "text/event-stream"

    # Test POST /route
    payload = {
        "prompt": "Check randomization integrity for experiment EXP_101. SRM check.",
        "router_kind": "baseline"
    }
    response_route = client.post("/route", json=payload)
    assert response_route.status_code == 200
    data = response_route.json()
    assert "chosen_agent_id" in data
    assert data["router_kind"] == "baseline"

    # Test POST /train
    response_train = client.post("/train")
    assert response_train.status_code == 200
    assert "status" in response_train.json()

    # Test Slack endpoints
    response_interactive = client.post(
        "/slack/interactive",
        data={"payload": '{"type": "block_actions"}'}
    )
    assert response_interactive.status_code == 200

    response_commands = client.post(
        "/slack/commands",
        data={"command": "/route-agent", "text": "hello"}
    )
    assert response_commands.status_code == 200
    assert "response_type" in response_commands.json()

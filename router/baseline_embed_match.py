import time

from common.schema import AgentDescriptor, RouteDecision, TaskFamily
from router.features import cosine_similarity, get_embedding


def route_baseline(
    request_id: str,
    prompt: str,
    task_family: TaskFamily,
    candidates: list[AgentDescriptor],
    cost_weight: float = 0.5
) -> RouteDecision:
    """
    Performs baseline routing using semantic similarity matching.
    Filters candidate agents that support the target TaskFamily, calculates
    cosine similarity between the prompt and the agent's capability text,
    and applies a penalty for agent cost:
        Score = Similarity - cost_weight * (cost_per_1k_tokens * 50)
    """
    start_time = time.time()
    scored_candidates = []

    prompt_emb = get_embedding(prompt)

    for agent in candidates:
        if task_family not in agent.task_families:
            continue

        cap_emb = get_embedding(agent.capability_text)
        sim = cosine_similarity(prompt_emb, cap_emb)

        # Scale cost so it has comparable magnitude to similarity (range ~0 to 1)
        cost_penalty = agent.cost_per_1k_tokens * 50.0
        score = sim - (cost_weight * cost_penalty)

        scored_candidates.append({
            "agent_id": agent.agent_id,
            "score": score,
            "predicted_cost": agent.cost_per_1k_tokens,
            "predicted_quality": sim
        })

    if not scored_candidates:
        raise ValueError(f"No candidate agents support task family: {task_family}")

    # Sort descending by score
    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    best = scored_candidates[0]

    explanation = (
        f"Selected agent '{best['agent_id']}' (similarity: {best['predicted_quality']:.2f}, "
        f"cost: {best['predicted_cost']:.6f})."
    )

    return RouteDecision(
        request_id=request_id,
        chosen_agent_id=best["agent_id"],
        router_kind="baseline",
        score=best["score"],
        explanation=explanation,
        candidates=scored_candidates,
        decision_latency_ms=(time.time() - start_time) * 1000
    )

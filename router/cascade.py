import time
from datetime import datetime, timedelta

import numpy as np

from common.bq import query_eval_scores, query_signals
from common.schema import AgentDescriptor, RouteDecision, TaskFamily
from router.features import build_features
from router.learned_router import LearnedRouter


def route_cascade(
    request_id: str,
    prompt: str,
    task_family: TaskFamily,
    candidates: list[AgentDescriptor],
    confidence_threshold: float = 0.85
) -> RouteDecision:
    """
    Implements cascading routing. Candidates are sorted by cost (cheapest first).
    We estimate the success probability (confidence) for each agent starting from the cheapest.
    If the estimated confidence is >= confidence_threshold, we select that agent.
    Otherwise, we escalate to the next candidate.
    If all candidates fail to meet the threshold, we select the last (most expensive) candidate.
    """
    start_time = time.time()

    # Filter candidates by task family
    valid_candidates = [c for c in candidates if task_family in c.task_families]
    if not valid_candidates:
        raise ValueError(f"No candidate agents support task family: {task_family}")

    # Sort by cost ascending
    valid_candidates.sort(key=lambda x: x.cost_per_1k_tokens)

    # Try to load the learned router to estimate success probability
    learned_router = LearnedRouter()

    # Cache DB lookups for routing decision
    since = datetime.utcnow() - timedelta(hours=24)
    cached_evals = query_eval_scores(since)
    cached_signals = query_signals(since)

    scored_candidates = []
    chosen_agent = None
    explanation = ""

    for idx, agent in enumerate(valid_candidates):
        # Build features for this request and candidate agent
        features = build_features(
            prompt,
            agent,
            cached_evals=cached_evals,
            cached_signals=cached_signals
        )

        # Estimate quality / confidence (P(success))
        if learned_router.model is not None:
            feature_vector = np.array([[
                features["semantic_similarity"],
                features["cost_per_1k"],
                features["mean_pass_rate"],
                features["failure_signal_rate"]
            ]])
            p_success = float(learned_router.model.predict(feature_vector)[0])
            est_source = "LightGBM model"
        else:
            p_success = features["mean_pass_rate"]
            est_source = "historical pass rate"

        scored_candidates.append({
            "agent_id": agent.agent_id,
            "score": p_success,
            "predicted_cost": agent.cost_per_1k_tokens,
            "predicted_quality": p_success
        })

        # Determine if we should stop at this agent or escalate
        # If it is the last agent, we must select it
        is_last = (idx == len(valid_candidates) - 1)
        if p_success >= confidence_threshold or is_last:
            chosen_agent = agent
            if is_last and p_success < confidence_threshold:
                explanation = (
                    f"Escalated to final fallback agent '{agent.agent_id}' "
                    f"(cost: {agent.cost_per_1k_tokens:.6f}) as no earlier agent "
                    f"met confidence threshold of {confidence_threshold:.2f} "
                    f"(predicted: {p_success:.2f} via {est_source})."
                )
            else:
                explanation = (
                    f"Selected cheap agent '{agent.agent_id}' "
                    f"(cost: {agent.cost_per_1k_tokens:.6f}) because its "
                    f"predicted confidence of {p_success:.2f} (via {est_source}) "
                    f"met threshold of {confidence_threshold:.2f}."
                )
            break

    # If for some reason chosen_agent is not set (should not happen due to is_last check)
    if not chosen_agent:
        chosen_agent = valid_candidates[-1]
        explanation = f"Fallback selected the most expensive agent '{chosen_agent.agent_id}'."

    return RouteDecision(
        request_id=request_id,
        chosen_agent_id=chosen_agent.agent_id,
        router_kind="cascade",
        score=confidence_threshold,  # we report the threshold or the chosen agent's score
        explanation=explanation,
        candidates=scored_candidates,
        decision_latency_ms=(time.time() - start_time) * 1000
    )

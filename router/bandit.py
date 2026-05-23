import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from common.bq import get_sqlite_conn, query_eval_scores, query_signals
from common.schema import AgentDescriptor, RouteDecision, TaskFamily
from router.features import build_features


class BanditRouter:
    def __init__(self, alpha: float = 1.5):
        self.alpha = alpha
        self.A = {}  # agent_id -> d x d matrix
        self.b = {}  # agent_id -> d x 1 vector
        self.d = 4   # number of features

    def update_from_db(self) -> None:
        """
        Queries the historical responses from the database and updates the LinUCB
        context matrices A and b for each agent.
        """
        conn = get_sqlite_conn()
        query = "SELECT agent_id, success FROM agent_responses WHERE success IS NOT NULL"
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Load active agents to resolve capabilities and costs
        from mesh.registry import list_all_agents
        agents_map = {a.agent_id: a for a in list_all_agents()}

        # Initialize matrices
        self.A = {}
        self.b = {}

        for agent_id, agent in agents_map.items():
            self.A[agent_id] = np.identity(self.d)
            self.b[agent_id] = np.zeros((self.d, 1))

        # Cache DB evaluation and signal queries once for the batch
        since = datetime.utcnow() - timedelta(hours=24)
        cached_evals = query_eval_scores(since)
        cached_signals = query_signals(since)

        # Update matrices with historical logs
        for _, row in df.iterrows():
            agent_id = row["agent_id"]
            if agent_id not in agents_map:
                continue
            agent = agents_map[agent_id]

            # Reconstruct feature vector
            features = build_features(
                agent.capability_text,
                agent,
                cached_evals=cached_evals,
                cached_signals=cached_signals
            )
            x = np.array([[
                features["semantic_similarity"],
                features["cost_per_1k"],
                features["mean_pass_rate"],
                features["failure_signal_rate"]
            ]]).T  # Shape: (d, 1)

            y = float(row["success"])

            self.A[agent_id] += np.dot(x, x.T)
            self.b[agent_id] += y * x

    def route(
        self,
        request_id: str,
        prompt: str,
        task_family: TaskFamily,
        candidates: list[AgentDescriptor],
        update_db: bool = True
    ) -> RouteDecision:
        """
        Calculates LinUCB score for each candidate agent and selects the one with the maximum score.
        For cold-start agents (< 20 runs in database), ensures they receive exploration priority.
        """
        start_time = time.time()

        # Build matrices from DB if requested or not loaded
        if update_db or not self.A:
            self.update_from_db()

        # Count runs per agent to identify cold-start candidates
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_id, COUNT(*) FROM agent_responses "
            "WHERE success IS NOT NULL GROUP BY agent_id"
        )
        run_counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        scored_candidates = []
        cold_start_candidates = []

        # Cache DB lookups for routing decision
        since = datetime.utcnow() - timedelta(hours=24)
        cached_evals = query_eval_scores(since)
        cached_signals = query_signals(since)

        for agent in candidates:
            if task_family not in agent.task_families:
                continue

            agent_id = agent.agent_id
            run_count = run_counts.get(agent_id, 0)

            # Ensure agent matrices exist
            if agent_id not in self.A:
                self.A[agent_id] = np.identity(self.d)
                self.b[agent_id] = np.zeros((self.d, 1))

            features = build_features(
                prompt,
                agent,
                cached_evals=cached_evals,
                cached_signals=cached_signals
            )
            x = np.array([[
                features["semantic_similarity"],
                features["cost_per_1k"],
                features["mean_pass_rate"],
                features["failure_signal_rate"]
            ]]).T  # Shape: (d, 1)

            # Calculate LinUCB parameters
            A_inv = np.linalg.inv(self.A[agent_id])
            theta = np.dot(A_inv, self.b[agent_id])

            # Expected value
            expected_payoff = float(np.dot(theta.T, x)[0, 0])
            # Variance / Uncertainty
            uncertainty = float(np.sqrt(np.dot(x.T, np.dot(A_inv, x))[0, 0]))

            # LinUCB score
            score = expected_payoff + self.alpha * uncertainty

            # If it's a cold-start agent, we track it separately or boost its score
            is_cold_start = run_count < 20

            candidate_info = {
                "agent_id": agent_id,
                "score": score,
                "predicted_cost": agent.cost_per_1k_tokens,
                "predicted_quality": expected_payoff,
                "uncertainty": uncertainty,
                "run_count": run_count,
                "is_cold_start": is_cold_start
            }

            if is_cold_start:
                cold_start_candidates.append(candidate_info)
            else:
                scored_candidates.append(candidate_info)

        # Priority routing: if there are cold-start candidates, choose the one with
        # the highest uncertainty or lowest run count to speed up convergence.
        # Otherwise, choose the overall best score.
        if cold_start_candidates:
            # Sort cold start candidates: fewest runs first, then highest uncertainty
            cold_start_candidates.sort(key=lambda x: (x["run_count"], -x["uncertainty"]))
            best = cold_start_candidates[0]
            explanation_prefix = "Cold-start exploration prioritized"
        else:
            if not scored_candidates:
                raise ValueError(f"No candidate agents support task family: {task_family}")
            # Sort by score descending
            scored_candidates.sort(key=lambda x: x["score"], reverse=True)
            best = scored_candidates[0]
            explanation_prefix = "LinUCB exploitation"

        explanation = (
            f"{explanation_prefix} for agent '{best['agent_id']}' (score: {best['score']:.4f}, "
            f"expected payoff: {best['predicted_quality']:.4f}, "
            f"uncertainty: {best['uncertainty']:.4f}, runs: {best['run_count']})."
        )

        # Merge and format candidates for the RouteDecision output schema
        all_options = cold_start_candidates + scored_candidates
        candidates_out = [
            {
                "agent_id": c["agent_id"],
                "score": c["score"],
                "predicted_cost": c["predicted_cost"],
                "predicted_quality": c["predicted_quality"]
            }
            for c in all_options
        ]

        return RouteDecision(
            request_id=request_id,
            chosen_agent_id=best["agent_id"],
            router_kind="bandit",
            score=best["score"],
            explanation=explanation,
            candidates=candidates_out,
            decision_latency_ms=(time.time() - start_time) * 1000
        )

def route_bandit(
    request_id: str,
    prompt: str,
    task_family: TaskFamily,
    candidates: list[AgentDescriptor],
    alpha: float = 1.5,
    update_db: bool = True
) -> RouteDecision:
    router = BanditRouter(alpha=alpha)
    return router.route(request_id, prompt, task_family, candidates, update_db=update_db)

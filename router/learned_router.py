import os
import pickle
import time
from datetime import datetime, timedelta

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.bq import get_sqlite_conn, query_eval_scores, query_signals
from common.schema import AgentDescriptor, RouteDecision, TaskFamily
from router.baseline_embed_match import route_baseline
from router.features import build_features

MODEL_FILE = "learned_router.pkl"

class LearnedRouter:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self) -> None:
        if os.path.exists(MODEL_FILE):
            try:
                with open(MODEL_FILE, "rb") as f:
                    self.model = pickle.load(f)
            except Exception as e:
                print(f"[LearnedRouter] Failed to load model: {e}")

    def save_model(self) -> None:
        try:
            with open(MODEL_FILE, "wb") as f:
                pickle.dump(self.model, f)
        except Exception as e:
            print(f"[LearnedRouter] Failed to save model: {e}")

    def train(self) -> bool:
        """
        Trains the LightGBM classifier predicting P(success | request, agent)
        from historical SQLite database traces.
        """
        conn = get_sqlite_conn()
        # Retrieve historical responses that have a resolved success value
        query = (
            "SELECT request_id, agent_id, success, timestamp "
            "FROM agent_responses WHERE success IS NOT NULL"
        )
        df = pd.read_sql_query(query, conn)
        conn.close()

        if len(df) < 30:
            print(
                f"[LearnedRouter] Insufficient training data ({len(df)} rows). "
                "Requires >= 30. Skipping."
            )
            return False

        # Load active agents to resolve capabilities and costs
        from mesh.registry import list_all_agents
        agents_map = {a.agent_id: a for a in list_all_agents()}

        # Cache DB evaluation and signal queries once for the batch
        since = datetime.utcnow() - timedelta(hours=24)
        cached_evals = query_eval_scores(since)
        cached_signals = query_signals(since)

        X = []
        y = []

        for _, row in df.iterrows():
            agent_id = row["agent_id"]
            if agent_id not in agents_map:
                continue
            agent = agents_map[agent_id]

            # Since historical prompts aren't in agent_responses,
            # we use the agent's capability text as a surrogate prompt for feature extraction
            features = build_features(
                agent.capability_text,
                agent,
                cached_evals=cached_evals,
                cached_signals=cached_signals
            )

            X.append([
                features["semantic_similarity"],
                features["cost_per_1k"],
                features["mean_pass_rate"],
                features["failure_signal_rate"]
            ])
            y.append(int(row["success"]))

        if len(X) < 10:
            return False

        X_np = np.array(X)
        y_np = np.array(y)

        # Train a lightgbm binary classifier
        train_data = lgb.Dataset(X_np, label=y_np)
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "min_data_in_leaf": 5,
            "learning_rate": 0.05
        }
        self.model = lgb.train(params, train_data, num_boost_round=50)
        self.save_model()
        print("[LearnedRouter] LightGBM model successfully trained.")
        return True

    def route(
        self,
        request_id: str,
        prompt: str,
        task_family: TaskFamily,
        candidates: list[AgentDescriptor],
        lambda_val: float = 0.5
    ) -> RouteDecision:
        """
        Predicts success probability for each candidate using the trained LightGBM model.
        Scores candidate agents using cost-weighted argmax:
            Score = P(success) / ((cost_per_1k + 1e-6) ** lambda_val)
        Falls back to baseline routing if the model is not trained.
        """
        if not self.model:
            # Fallback if model hasn't been trained yet
            return route_baseline(request_id, prompt, task_family, candidates)

        start_time = time.time()
        scored_candidates = []

        # Cache DB lookups for routing decision
        since = datetime.utcnow() - timedelta(hours=24)
        cached_evals = query_eval_scores(since)
        cached_signals = query_signals(since)

        for agent in candidates:
            if task_family not in agent.task_families:
                continue

            features = build_features(
                prompt,
                agent,
                cached_evals=cached_evals,
                cached_signals=cached_signals
            )
            feature_vector = np.array([[
                features["semantic_similarity"],
                features["cost_per_1k"],
                features["mean_pass_rate"],
                features["failure_signal_rate"]
            ]])

            # Predict P(success)
            p_success = float(self.model.predict(feature_vector)[0])

            # argmax P(success) / (cost ** lambda)
            # Add epsilon to prevent division by zero
            eps = 1e-6
            cost = agent.cost_per_1k_tokens
            score = p_success / ((cost + eps) ** lambda_val)

            scored_candidates.append({
                "agent_id": agent.agent_id,
                "score": score,
                "predicted_cost": cost,
                "predicted_quality": p_success
            })

        if not scored_candidates:
            raise ValueError(f"No candidate agents support task family: {task_family}")

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        best = scored_candidates[0]

        explanation = (
            f"Selected agent '{best['agent_id']}' via LightGBM P(success) "
            f"optimization (predicted P(success): {best['predicted_quality']:.2f}, "
            f"cost: {best['predicted_cost']:.6f})."
        )

        return RouteDecision(
            request_id=request_id,
            chosen_agent_id=best["agent_id"],
            router_kind="learned",
            score=best["score"],
            explanation=explanation,
            candidates=scored_candidates,
            decision_latency_ms=(time.time() - start_time) * 1000
        )

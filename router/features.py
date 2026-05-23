import functools
import hashlib
from datetime import datetime, timedelta

import numpy as np

from common.bq import query_eval_scores, query_signals
from common.config import settings
from common.schema import AgentDescriptor


@functools.lru_cache(maxsize=1024)
def get_embedding(text: str) -> list[float]:
    """
    Returns a 768-dimensional embedding for a given text.
    In MOCK=true mode, returns a deterministic unit-length vector.
    In MOCK=false mode, calls the Gemini Embedding API.
    """
    if settings.mock:
        # Generate deterministic mock embedding of length 768
        vals = []
        for i in range(96):  # 96 * 8 = 768 dimensions
            h = hashlib.md5(f"{text}-{i}".encode("utf-8")).hexdigest()
            for j in range(8):
                val = int(h[j*4:(j+1)*4], 16) / 65535.0
                vals.append(val)
        arr = np.array(vals)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()
    else:
        try:
            from google import genai
            client = genai.Client(project=settings.gcp.project_id)
            resp = client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            # text-embedding-004 standard returns 768 dimensions
            return resp.embeddings[0].values
        except Exception as e:
            # Fallback to mock if API fails
            print(f"[Embedding Error] Fallback to mock embedding: {e}")
            return get_embedding(text)

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a1 = np.array(v1)
    a2 = np.array(v2)
    dot = np.dot(a1, a2)
    n1 = np.linalg.norm(a1)
    n2 = np.linalg.norm(a2)
    if n1 > 0 and n2 > 0:
        return float(dot / (n1 * n2))
    return 0.0

def build_features(
    prompt: str,
    agent: AgentDescriptor,
    lookback_hours: int = 24,
    cached_evals: list = None,
    cached_signals: list = None
) -> dict:
    """
    Constructs a feature dictionary for the (request prompt, candidate agent) pair.
    Extracted features:
      - semantic_similarity: Cosine similarity between prompt and agent capabilities
      - cost_per_1k: Agent execution cost
      - mean_pass_rate: Historical pass rate from eval_scores
      - failure_signal_rate: Frequency of failure signals over the lookback window
    """
    prompt_emb = get_embedding(prompt)
    cap_emb = get_embedding(agent.capability_text)
    similarity = cosine_similarity(prompt_emb, cap_emb)

    since = datetime.utcnow() - timedelta(hours=lookback_hours)

    # 1. Historical eval pass rate
    evals = cached_evals if cached_evals is not None else query_eval_scores(since)
    agent_evals = [e.pass_k for e in evals if e.agent_id == agent.agent_id]
    mean_pass_rate = float(np.mean(agent_evals)) if agent_evals else 0.95  # default healthy

    # 2. Recent failure signals rate
    sigs = cached_signals if cached_signals is not None else query_signals(since)
    agent_sigs = [s for s in sigs if s.agent_id == agent.agent_id]

    # Track critical failure indicators (refusal, task_failure,
    # out_of_bounds, low_confidence_output, self_report)
    failures = [
        s for s in agent_sigs
        if s.kind in (
            "refusal", "task_failure", "out_of_bounds",
            "low_confidence_output", "self_report"
        )
    ]
    failure_signal_rate = len(failures) / max(len(agent_sigs), 1)

    return {
        "semantic_similarity": similarity,
        "cost_per_1k": agent.cost_per_1k_tokens,
        "mean_pass_rate": mean_pass_rate,
        "failure_signal_rate": failure_signal_rate,
    }

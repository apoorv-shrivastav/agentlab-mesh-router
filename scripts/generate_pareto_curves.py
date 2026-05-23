import os

import numpy as np
import pandas as pd
import yaml

from common.bq import get_sqlite_conn
from common.schema import TaskFamily
from mesh.registry import list_all_agents
from router.bandit import route_bandit
from router.baseline_embed_match import route_baseline
from router.learned_router import LearnedRouter

TASKS_DIR = "harness/tasks"

def load_all_tasks() -> list[dict]:
    tasks = []
    # Data Prep
    dp_path = os.path.join(TASKS_DIR, "data_prep.yaml")
    if os.path.exists(dp_path):
        with open(dp_path, "r") as f:
            for t in yaml.safe_load(f):
                t["task_family"] = TaskFamily.DATA_PREP
                tasks.append(t)
    # Causal Estimation
    ce_path = os.path.join(TASKS_DIR, "causal_estimation.yaml")
    if os.path.exists(ce_path):
        with open(ce_path, "r") as f:
            for t in yaml.safe_load(f):
                t["task_family"] = TaskFamily.CAUSAL_ESTIMATION
                tasks.append(t)
    # Readout
    ro_path = os.path.join(TASKS_DIR, "readout.yaml")
    if os.path.exists(ro_path):
        with open(ro_path, "r") as f:
            for t in yaml.safe_load(f):
                t["task_family"] = TaskFamily.READOUT
                tasks.append(t)
    return tasks

def get_latest_agent_qualities() -> dict:
    """Gets the latest pass_k score for each (agent_id, task_family) from the DB."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT agent_id, task_family, pass_k, MAX(timestamp)
        FROM eval_scores
        GROUP BY agent_id, task_family
    """)
    rows = cursor.fetchall()
    conn.close()

    qualities = {}
    for r in rows:
        qualities[(r[0], r[1])] = r[2]

    # Add defaults if not seeded
    for agent in list_all_agents():
        for tf in agent.task_families:
            key = (agent.agent_id, tf.value)
            if key not in qualities:
                # Spare agents default to healthy (0.95), degraded ones are handled by DB
                qualities[key] = 0.95

    return qualities

def run_simulation():
    print("Loading test tasks from golden sets...")
    tasks = load_all_tasks()
    print(f"Loaded {len(tasks)} tasks.")

    print("\nRetrieving agent quality profiles from database...")
    qualities = get_latest_agent_qualities()
    agents = list_all_agents()
    agents_map = {a.agent_id: a for a in agents}

    print("\nAgent quality map:")
    for k, v in qualities.items():
        print(f"  Agent: {k[0]} | Task Family: {k[1]} | Latest Quality: {v:.2%}")

    # Ensure LightGBM router is trained
    print("\nTraining Learned Router...")
    lr = LearnedRouter()
    lr.train()

    results = []

    # 1. Baseline Router parameter sweep
    print("\nSimulating Baseline Router...")
    for cost_w in [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0]:
        costs = []
        quals = []
        for idx, task in enumerate(tasks):
            tf = task["task_family"]
            dec = route_baseline(
                request_id=f"sim-base-{idx}",
                prompt=task["prompt"],
                task_family=tf,
                candidates=agents,
                cost_weight=cost_w
            )
            agent_id = dec.chosen_agent_id
            costs.append(agents_map[agent_id].cost_per_1k_tokens)
            quals.append(qualities.get((agent_id, tf.value), 0.95))
        results.append({
            "Router": f"Baseline (cost_weight={cost_w})",
            "Avg Cost ($/1k)": np.mean(costs),
            "Avg Quality (Pass Rate)": np.mean(quals)
        })

    # 2. Learned Router parameter sweep
    print("Simulating Learned Router...")
    for lambda_val in [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0]:
        costs = []
        quals = []
        for idx, task in enumerate(tasks):
            tf = task["task_family"]
            dec = lr.route(
                request_id=f"sim-learned-{idx}",
                prompt=task["prompt"],
                task_family=tf,
                candidates=agents,
                lambda_val=lambda_val
            )
            agent_id = dec.chosen_agent_id
            costs.append(agents_map[agent_id].cost_per_1k_tokens)
            quals.append(qualities.get((agent_id, tf.value), 0.95))
        results.append({
            "Router": f"Learned (lambda={lambda_val})",
            "Avg Cost ($/1k)": np.mean(costs),
            "Avg Quality (Pass Rate)": np.mean(quals)
        })

    # 3. Bandit Router parameter sweep
    print("Simulating Bandit Router...")
    for alpha in [0.1, 0.5, 1.0, 1.5, 2.0, 3.0]:
        costs = []
        quals = []
        for idx, task in enumerate(tasks):
            tf = task["task_family"]
            dec = route_bandit(
                request_id=f"sim-bandit-{idx}",
                prompt=task["prompt"],
                task_family=tf,
                candidates=agents,
                alpha=alpha,
                update_db=(idx == 0)
            )
            agent_id = dec.chosen_agent_id
            costs.append(agents_map[agent_id].cost_per_1k_tokens)
            quals.append(qualities.get((agent_id, tf.value), 0.95))
        results.append({
            "Router": f"Bandit (alpha={alpha})",
            "Avg Cost ($/1k)": np.mean(costs),
            "Avg Quality (Pass Rate)": np.mean(quals)
        })

    # Print results table
    df_res = pd.DataFrame(results)
    print("\n### Router Cost vs Quality Pareto Curve Evaluation ###")
    print(df_res.to_string(index=False))

if __name__ == "__main__":
    run_simulation()

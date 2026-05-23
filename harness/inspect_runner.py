from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

from common.bq import write_eval_score
from common.schema import AgentRequest, EvalScore, TaskFamily
from harness.scorers.end_state import score_end_state


def load_tasks_from_yaml(task_family: TaskFamily) -> list[dict]:
    """Loads golden set tasks for the specific step task family."""
    yaml_path = Path(__file__).resolve().parent / "tasks" / f"{task_family.value}.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Task file not found at {yaml_path}")
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)

def bootstrap_confidence_interval(
    data: list[float],
    n_bootstrap: int = 1000,
    alpha: float = 0.05
) -> tuple[float, float]:
    """Computes standard non-parametric bootstrap confidence intervals."""
    if not data:
        return 0.0, 0.0
    boot_means = []
    # Set seed for reproducible validation checks
    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        sample = rng.choice(data, size=len(data), replace=True)
        boot_means.append(np.mean(sample))
    ci_low = float(np.percentile(boot_means, 100 * (alpha / 2)))
    ci_high = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return ci_low, ci_high

def run_evaluation(
    agent,
    task_family: TaskFamily,
    n_trials: int = 5
) -> EvalScore:
    """
    Evaluates an agent over its respective task family.
    Runs each task n_trials times, calculates pass_k, bootstraps CIs,
    and logs the EvalScore to the database.
    """
    tasks = load_tasks_from_yaml(task_family)
    task_successes = []

    for task in tasks:
        task_id = task["id"]
        prompt = task["prompt"]
        expected = task["expected"]

        trial_scores = []
        for trial in range(n_trials):
            req = AgentRequest(
                request_id=f"eval-{task_id}-trial-{trial}",
                prompt=prompt,
                task_family=task_family
            )
            resp = agent.handle(req)
            success = score_end_state(resp, expected)
            trial_scores.append(1.0 if success else 0.0)

        # Calculate task score (average pass rate for this task)
        task_score = np.mean(trial_scores)
        task_successes.append(task_score)

    # pass_k is defined as the mean success rate across all evaluation cases
    pass_k = float(np.mean(task_successes))
    ci_low, ci_high = bootstrap_confidence_interval(task_successes)

    score = EvalScore(
        agent_id=agent.descriptor.agent_id,
        task_family=task_family,
        pass_k=pass_k,
        n_trials=len(tasks) * n_trials,
        ci_low=ci_low,
        ci_high=ci_high,
        timestamp=datetime.utcnow()
    )

    # Save to SQLite/BigQuery
    write_eval_score(score)
    return score

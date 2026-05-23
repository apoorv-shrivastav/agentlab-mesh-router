import sqlite3
from datetime import datetime
import numpy as np
from scipy.stats import binom, chi2
from common.config import settings

def mcnemar_test(base_outcomes: list[int], comp_outcomes: list[int]) -> float:
    """
    Computes McNemar's test p-value for paired nominal data.
    Uses exact binomial calculation for small sample sizes (discordant cells < 25),
    and chi-squared test with continuity correction otherwise.
    """
    if len(base_outcomes) != len(comp_outcomes):
        raise ValueError("Baseline and comparison outcomes must be paired and of equal length.")
        
    # Count contingency table:
    #                 comp = 1   comp = 0
    #   base = 1         n11        n10
    #   base = 0         n01        n00
    n10 = 0 # base succeeded, comp failed
    n01 = 0 # base failed, comp succeeded
    
    for b, c in zip(base_outcomes, comp_outcomes):
        if b == 1 and c == 0:
            n10 += 1
        elif b == 0 and c == 1:
            n01 += 1
            
    total_discordant = n10 + n01
    if total_discordant == 0:
        return 1.0
        
    if total_discordant < 25:
        # Exact binomial test under H0: p = 0.5
        p_val = 2.0 * binom.cdf(min(n10, n01), total_discordant, 0.5)
        # Handle boundary case where binom.cdf exceeds 0.5
        return min(p_val, 1.0)
    else:
        # Chi-squared test with continuity correction
        stat = (abs(n10 - n01) - 0.5) ** 2 / total_discordant
        p_val = 1.0 - chi2.cdf(stat, df=1)
        return p_val

def bootstrap_difference_ci(
    base_outcomes: list[int],
    comp_outcomes: list[int],
    alpha: float = 0.05,
    B: int = 1000
) -> tuple[float, float, float]:
    """
    Computes the mean difference (comp - base) and its bootstrap confidence interval.
    """
    if len(base_outcomes) != len(comp_outcomes):
        raise ValueError("Baseline and comparison outcomes must be paired and of equal length.")
        
    n = len(base_outcomes)
    if n == 0:
        return 0.0, 0.0, 0.0
        
    diffs = np.array(comp_outcomes) - np.array(base_outcomes)
    mean_diff = float(np.mean(diffs))
    
    # Set seed for reproducible tests
    rng = np.random.default_rng(42)
    boot_diffs = []
    for _ in range(B):
        sample_indices = rng.choice(n, size=n, replace=True)
        boot_diffs.append(np.mean(diffs[sample_indices]))
        
    ci_low = float(np.percentile(boot_diffs, 100 * (alpha / 2)))
    ci_high = float(np.percentile(boot_diffs, 100 * (1.0 - alpha / 2)))
    
    return mean_diff, ci_low, ci_high

def benjamini_hochberg(p_values: dict[str, float], alpha_fdr: float = 0.05) -> dict[str, bool]:
    """
    Performs Benjamini-Hochberg False Discovery Rate (FDR) correction on a dictionary of p-values.
    Returns a dictionary mapping keys to a boolean indicating if the null hypothesis is rejected.
    """
    if not p_values:
        return {}
        
    sorted_items = sorted(p_values.items(), key=lambda x: x[1])
    m = len(sorted_items)
    
    max_k = -1
    for k, (key, p_val) in enumerate(sorted_items):
        # 1-indexed formula rank is k + 1
        threshold = ((k + 1) / m) * alpha_fdr
        if p_val <= threshold:
            max_k = k
            
    rejections = {key: False for key in p_values.keys()}
    if max_k != -1:
        # Reject all null hypotheses up to rank max_k
        for k in range(max_k + 1):
            rejections[sorted_items[k][0]] = True
            
    return rejections

def detect_regressions_from_db(
    db_file: str = "agentlab.db",
    lookback_days: int = 7
) -> dict:
    """
    Queries evaluation trials in the DB and runs McNemar's test comparing
    baseline (first half of lookback window) vs comparison (second half of lookback window).
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Fetch all evaluation runs from the agent_responses table
    cursor.execute("""
        SELECT request_id, agent_id, success, timestamp
        FROM agent_responses
        WHERE request_id LIKE 'eval-%' AND success IS NOT NULL
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"status": "no_data", "regressions": {}}
        
    # Group results by agent_id and evaluation task-trial identifier
    # request_id format: eval-{task_id}-trial-{trial}
    evals = {}
    for req_id, agent_id, success, timestamp_str in rows:
        try:
            ts = datetime.fromisoformat(timestamp_str)
        except Exception:
            continue
            
        parts = req_id.split("-")
        if len(parts) < 4:
            continue
        # task_id is parts[1:-2], trial is parts[-1]
        task_id = "-".join(parts[1:-2])
        trial = parts[-1]
        pair_key = f"{task_id}-t{trial}"
        
        if agent_id not in evals:
            evals[agent_id] = []
        evals[agent_id].append((pair_key, success, ts))
        
    # Run McNemar's test for each agent by splitting history into baseline and comparison
    p_values = {}
    results = {}
    
    for agent_id, trials in evals.items():
        if len(trials) < 10:
            continue
            
        # Find split time (median timestamp)
        timestamps = sorted([t[2] for t in trials])
        median_time = timestamps[len(timestamps) // 2]
        
        # Partition trials by baseline and comparison
        base_map = {}
        comp_map = {}
        for pair_key, success, ts in trials:
            if ts <= median_time:
                base_map[pair_key] = success
            else:
                comp_map[pair_key] = success
                
        # Find common tasks across both periods
        common_keys = set(base_map.keys()).intersection(set(comp_map.keys()))
        if len(common_keys) < 5:
            continue
            
        base_list = [base_map[k] for k in common_keys]
        comp_list = [comp_map[k] for k in common_keys]
        
        # Compute stats
        p_val = mcnemar_test(base_list, comp_list)
        mean_diff, ci_low, ci_high = bootstrap_difference_ci(base_list, comp_list)
        
        p_values[agent_id] = p_val
        results[agent_id] = {
            "p_value": p_val,
            "mean_diff": mean_diff,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "sample_size": len(common_keys)
        }
        
    # Apply Benjamini-Hochberg FDR correction
    rejections = benjamini_hochberg(p_values)
    for agent_id in results.keys():
        results[agent_id]["regression_detected"] = rejections.get(agent_id, False) and (results[agent_id]["mean_diff"] < 0)
        
    return {
        "status": "success",
        "regressions": results
    }

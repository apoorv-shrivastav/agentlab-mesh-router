# AgentLab Evaluation Methodology & Scientific Pre-registration

This document serves as our pre-registered evaluation protocol, defining the hypotheses, statistical decision boundaries, and evaluation metrics for AgentLab.

---

## 1. Primary Hypotheses & Success Criteria

### Hypothesis H1: Pareto Efficiency Frontier
* **Statement**: The learned routing policy (LightGBM) achieves a Pareto efficiency frontier that dominates the baseline match policy.
* **Metric**: Pareto dominance across API query cost vs. workflow execution quality (pass rate).
* **Success Criterion**: At any given quality target, the learned router reduces cost by $\ge 30\%$, and at any given budget target, it achieves equal or higher quality with no statistical crossovers.

### Hypothesis H2: Telemetry Sentry Overhead
* **Statement**: The online telemetry signal layer (regex scanning, explicit metric collectors, and DistilBERT token classifiers) is computationally and financially lightweight.
* **Metric**: Total token consumption and execution latency of signals per request trace.
* **Success Criterion**: Average telemetry token cost per trace is $\le 0.1\%$ of a full LLM-as-a-judge evaluation call on the same trace, and CPU inference latency is $\le 200\text{ms}$.

### Hypothesis H3: Statistical Regression Detection Sensitivity
* **Statement**: The offline sentry module correctly identifies task-family level performance regressions using paired McNemar tests.
* **Metric**: Statistical power to detect a true $\ge 20\%$ regression on evaluation sets.
* **Success Criterion**: True positive rate (sensitivity) $\ge 0.85$ at a family-wise error rate (FWER) controlled at $\alpha = 0.05$ after applying Benjamini-Hochberg False Discovery Rate (FDR) corrections.

### Hypothesis H4: Online Shift Detection Latency
* **Statement**: The online sentry module flags model drift and silent failures in signal rates using CUSUM and EWMA control charts.
* **Metric**: Average Run Length (ARL) until detection.
* **Success Criterion**: Detection occurs within 30 simulated minutes (or $\le 20$ requests) of the degradation injection, with a false-positive rate under $5\%$ on stable control flows.

### Hypothesis H5: Self-Healing Recovery Significance
* **Statement**: The autonomous triage and spares rerouting loop yields a statistically significant recovery in overall pipeline quality.
* **Metric**: Causal pass-rate improvement post-reroute.
* **Success Criterion**: The post-recovery pass rate is statistically equivalent to the pre-degradation healthy baseline, with a $95\%$ bootstrap confidence interval excluding zero for the recovery delta.

---

## 2. Statistical Decision Rules

### McNemar's Test for Paired Regressions
For pre/post upgrade evaluation pairs on the same task IDs, we construct a $2\times 2$ contingency table:

| | Post Pass | Post Fail |
|---|---|---|
| **Pre Pass** | $a$ | $b$ (regression) |
| **Pre Fail** | $c$ | $d$ |

- If $b + c < 25$, we compute the **Exact Binomial Test** under $H_0: p = 0.5$ where the p-value is:
  $$p = 2 \times \sum_{k=0}^{\min(b,c)} \binom{b+c}{k} 0.5^{b+c}$$
- If $b + c \ge 25$, we use McNemar's chi-squared test with continuity correction:
  $$\chi^2 = \frac{(|b - c| - 1)^2}{b + c}$$

### Benjamini-Hochberg FDR Control
When evaluating multiple task families, p-values are sorted $p_1 \le p_2 \le \dots \le p_m$. The regression is flagged if:
$$p_i \le \frac{i}{m} Q$$
where the FDR target is set at $Q = 0.05$.

### CUSUM & EWMA Online Control Limits
For a stream of signal rates $x_t$, the EWMA statistic is:
$$z_t = \lambda x_t + (1 - \lambda) z_{t-1}$$
We set the smoothing factor $\lambda = 0.2$ and trigger alarms when $z_t$ exceeds $3\sigma$ control boundaries.
For CUSUM, cumulative positive deviations are tracked:
$$S_t = \max(0, S_{t-1} + x_t - \mu_0 - K)$$
where $K = 0.5\sigma$ is the reference value and the alarm threshold is $H = 4\sigma$.
